import subprocess
import tempfile
import os
from enum import Enum, auto
from threading import Thread
from queue import Queue, Empty
from script.argument import *
from log.mm_logging import loggingContext, logError, exceptionStr
from locking.locking import lockContext
from script.script_error import ScriptError

NONE = 0
BLOCK = 2**0
DEBOUNCE = 2**1
SCRIPT_PATH_AS_ENV_VAR = 2**2
BACKGROUND = 2**3
KILL = 2**4

BLOCK_KEY = "BLOCK"
DEBOUNCE_KEY = "DEBOUNCE"
SCRIPT_PATH_AS_ENV_VAR_KEY = "SCRIPT_PATH_AS_ENV_VAR"
BACKGROUND_KEY = "BACKGROUND"
KILL_KEY = "KILL"

FLAGS = {
    BLOCK_KEY: BLOCK,
    DEBOUNCE_KEY: DEBOUNCE,
    SCRIPT_PATH_AS_ENV_VAR_KEY: SCRIPT_PATH_AS_ENV_VAR,
    BACKGROUND_KEY: BACKGROUND,
    KILL_KEY: KILL,
}
LOCK = "LOCK"
INVOCATION_FORMAT = "INVOCATION_FORMAT"


class FlagType(Enum):
    STRING_TYPE = auto()
    FSTRING_TYPE = auto()


KEY_VALUE_FLAGS = {
    LOCK: FlagType.STRING_TYPE,
    INVOCATION_FORMAT: FlagType.FSTRING_TYPE,
}
SCRIPT_PATH_ENV_VAR = "MM_SCRIPT"


class Script:
    def __init__(
        self,
        script,
        argumentDefinition,
        flags,
        keyValueFlags,
        interpreter,
        profile,
        subprofile=None,
    ):
        self.script = script
        self.argumentDefinition = argumentDefinition
        self.flags = flags
        self.keyValueFlags = keyValueFlags
        self.interpreter = interpreter
        self.profile = profile
        self.subprofile = subprofile
        self.invocationQueue = Queue()
        self.invocationThread = None
        self.locks = (
            self.keyValueFlags[LOCK].split(",") if LOCK in self.keyValueFlags else []
        )
        self.invocationFormat = (
            self.keyValueFlags[INVOCATION_FORMAT]
            if INVOCATION_FORMAT in self.keyValueFlags
            else None
        )
        self.argumentsOverSTDIN = (
            argumentDefinition.getShouldProcessArguments()
            or self.invocationFormat != None
        ) and not self.argumentDefinition.getReplaceString()
        self.scriptPathAsEnvVar = self.flags & SCRIPT_PATH_AS_ENV_VAR or (
            self.interpreter and self.argumentsOverSTDIN
        )
        self.scriptOverSTDIN = self.interpreter and not self.scriptPathAsEnvVar
        if self.flags & BACKGROUND:
            if self.argumentDefinition.getReplaceString():
                raise ScriptError(
                    f"{BACKGROUND_KEY} script cannot use a replace string"
                )
            if self.flags & DEBOUNCE:
                raise ScriptError(
                    f"{BACKGROUND_KEY} script cannot be used with {DEBOUNCE_KEY} enabled"
                )
            if self.flags & BLOCK:
                raise ScriptError(
                    f"{BACKGROUND_KEY} script cannot be used with {BLOCK_KEY} enabled"
                )
            if self.locks:
                raise ScriptError(f"{BACKGROUND_KEY} script cannot be used with {LOCK}")
        if self.flags & KILL:
            if not self.flags & BACKGROUND:
                raise ScriptError(
                    f"{KILL_KEY} can only be used on {BACKGROUND_KEY} scripts"
                )

    def lazyInitialize(self):
        if self.invocationThread:
            return
        if self.flags & BACKGROUND:
            (
                self.backgroundProcess,
                self.backgroundScriptPath,
            ) = self.spawnBackgroundProcess()
        self.invocationThread = Thread(target=self.invokeForever, daemon=True)
        self.invocationThread.start()

    def getScript(self):
        return self.script

    def getArgumentDefinition(self):
        return self.argumentDefinition

    def getFlags(self):
        return self.flags

    def getKeyValueFlags(self):
        return self.keyValueFlags

    def getInterpreter(self):
        return self.interpreter

    def getLocks(self):
        return self.locks

    def invokeForever(self):
        with loggingContext(self.profile, self.subprofile):
            shuttingDown = False
            while True:
                invocations = [self.invocationQueue.get()]
                try:
                    while True:
                        invocations.append(self.invocationQueue.get_nowait())
                except Empty:
                    pass
                # shutdown signal
                if invocations[-1] == None:
                    if len(invocations) == 1:
                        self.invocationQueue.task_done()
                        break
                    del invocations[-1]
                    shuttingDown = True
                if self.flags & DEBOUNCE:
                    self.invoke(invocations[-1])
                else:
                    for invocation in invocations:
                        self.invoke(invocation)
                for _ in range(len(invocations)):
                    self.invocationQueue.task_done()
                if shuttingDown:
                    self.invocationQueue.task_done()
                    break

    def removeScriptFile(self, scriptPath):
        try:
            os.remove(scriptPath)
        except FileNotFoundError:
            pass
        except Exception as exception:
            logError(
                f"could not remove script file: {scriptPath}, {exceptionStr(exception)}"
            )

    def shutdown(self):
        """
        Make sure all invocations of this script have been queued, and no more invocations will ever be queued, before calling this function.
        """
        if not self.invocationThread:
            return
        # signals to shutdown
        self.invocationQueue.put(None)
        self.invocationQueue.join()
        self.invocationThread.join()
        self.invocationThread = None
        if self.flags & BACKGROUND and self.backgroundProcess:
            if self.backgroundProcess.stdin and self.argumentsOverSTDIN:
                try:
                    self.backgroundProcess.stdin.close()
                except Exception:
                    pass
                if self.flags & KILL:
                    self.backgroundProcess.kill()
            else:
                self.backgroundProcess.kill()
            self.backgroundProcess.wait()
            if self.backgroundScriptPath:
                self.removeScriptFile(self.backgroundScriptPath)

    def spawnProcess(self, script):
        env = None
        scriptPath = None
        if self.scriptPathAsEnvVar:
            env = os.environ.copy()
            scriptFile = tempfile.NamedTemporaryFile(mode="w", delete=False)
            scriptFile.write(script)
            scriptFile.close()
            scriptPath = scriptFile.name
            env[SCRIPT_PATH_ENV_VAR] = scriptPath
        process = subprocess.Popen(
            self.interpreter if self.interpreter else script,
            stdin=(
                subprocess.PIPE
                if self.scriptOverSTDIN or self.argumentsOverSTDIN
                else None
            ),
            text=True,
            shell=True,
            start_new_session=True,
            env=env,
        )
        if process.stdin and self.scriptOverSTDIN:
            process.stdin.write(script)
            process.stdin.close()
        return process, scriptPath

    def spawnBackgroundProcess(self):
        backgroundProcess = None
        scriptPath = None
        try:
            backgroundProcess, scriptPath = self.spawnProcess(self.script)
        except Exception as exception:
            logError(f"failed to start background process: {exceptionStr(exception)}")
        return backgroundProcess, scriptPath

    def runProcess(self, processedScript, processedInput=None):
        with lockContext(self.locks):
            try:
                process, scriptPath = self.spawnProcess(processedScript)
                if process.stdin and self.argumentsOverSTDIN and processedInput:
                    process.stdin.write(processedInput)
                    process.stdin.close()
                if self.flags & BLOCK:
                    process.wait()
                    if scriptPath:
                        self.removeScriptFile(scriptPath)
            except Exception as exception:
                logError(f"failed to run script: {exceptionStr(exception)}")

    def formatArguments(self, arguments):
        if not self.invocationFormat:
            return arguments
        ARGUMENTS = arguments
        a = ARGUMENTS
        formattedArguments = eval(self.invocationFormat)
        if not isinstance(formattedArguments, str):
            raise ValueError
        return formattedArguments

    def invoke(self, context):
        trigger, arguments = context
        if (
            not self.argumentDefinition.getShouldProcessArguments()
            and self.invocationFormat == None
        ):
            if not self.flags & BACKGROUND:
                self.runProcess(self.script)
            return
        try:
            processedArguments = self.formatArguments(
                self.argumentDefinition.processArguments(trigger, arguments)
                if self.argumentDefinition.getShouldProcessArguments()
                else ""
            )
        except Exception:
            logError(
                f"failed to process arguments with argument format: {self.argumentDefinition.getArgumentFormat()} and invocation format: {self.invocationFormat}"
            )
            return
        replaceString = self.argumentDefinition.getReplaceString()
        if replaceString:
            self.runProcess(self.script.replace(replaceString, processedArguments))
        else:
            if self.flags & BACKGROUND and self.backgroundProcess:
                if self.backgroundProcess.stdin:
                    try:
                        self.backgroundProcess.stdin.write(processedArguments)
                        self.backgroundProcess.stdin.flush()
                    except Exception as exception:
                        logError(
                            f"failed to send arguments to background process: {exceptionStr(exception)}"
                        )
            else:
                self.runProcess(self.script, processedArguments)

    def queueIfArgumentsMatch(self, trigger, arguments):
        if not self.argumentDefinition.argumentsMatch(trigger, arguments):
            return
        self.queue(trigger, arguments)

    def queue(self, trigger, arguments):
        self.lazyInitialize()
        self.invocationQueue.put((trigger, arguments))

    def __str__(self):
        argumentDefinitionSpecification = f"{self.argumentDefinition} "
        interpreterSpecification = f'("{self.interpreter}")' if self.interpreter else ""
        flagsSpecification = (
            f"[{'|'.join(flag for flag in FLAGS if self.flags & FLAGS[flag])}]"
            if self.flags
            else ""
        )
        indentedScript = "\n".join(f"\t{line}" for line in self.script.splitlines())
        scriptSpecification = f"{{\n{indentedScript}\n}}"
        return f"{argumentDefinitionSpecification}{interpreterSpecification}{flagsSpecification}→\n{scriptSpecification}"
