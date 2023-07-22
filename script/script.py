import subprocess
from threading import Thread
from queue import Queue, Empty
from macro.macro_argument import MacroArgumentFormat
from log.mm_logging import logError, exceptionStr

NONE = 0
BLOCK = 2**0
DEBOUNCE = 2**1
FLAGS = {
    "BLOCK": BLOCK,
    "DEBOUNCE": DEBOUNCE,
}


class Script:
    def __init__(self, script, argumentDefinition, flags, interpreter):
        self.script = script
        self.argumentDefinition = argumentDefinition
        self.flags = flags
        self.interpreter = interpreter
        self.invocationQueue = Queue()
        self.invocationThread = None

    def lazyInitializeThread(self):
        if self.invocationThread:
            return
        self.invocationThread = Thread(target=self.invokeForever, daemon=True)
        self.invocationThread.start()

    def getScript(self):
        return self.script

    def getArgumentDefinition(self):
        return self.argumentDefinition

    def getFlags(self):
        return self.flags

    def getInterpreter(self):
        return self.interpreter

    def invokeForever(self):
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
                self.invokeScript(invocations[-1])
            else:
                for invocation in invocations:
                    self.invokeScript(invocation)
            for _ in range(len(invocations)):
                self.invocationQueue.task_done()
            if shuttingDown:
                self.invocationQueue.task_done()
                break

    def wait(self):
        if not self.invocationThread:
            return
        # signals to shutdown
        self.invocationQueue.put(None)
        self.invocationQueue.join()
        self.invocationThread.join()

    def runProcess(self, processedScript):
        try:
            process = subprocess.Popen(
                self.interpreter if self.interpreter else processedScript,
                stdin=subprocess.PIPE if self.interpreter else None,
                text=True,
                shell=True,
                start_new_session=True,
            )
            if self.interpreter:
                process.stdin.write(processedScript)
                process.stdin.close()
            if self.flags & BLOCK:
                process.wait()
        except Exception as exception:
            logError(f"failed to run script, {exceptionStr(exception)}")

    def invokeScript(self, args):
        if not self.argumentDefinition:
            self.runProcess(self.script)
            return
        argumentFormat = self.argumentDefinition.getArgumentFormat()
        replaceString = self.argumentDefinition.getReplaceString()
        if isinstance(argumentFormat, MacroArgumentFormat):
            argumentGenerator = (
                argumentFormat.toMacroArgument(playedNote) for playedNote in args
            )
        else:
            argumentGenerator = (
                "".join(
                    af if isinstance(af, str) else af.toMacroArgument(playedNote)
                    for af in argumentFormat
                )
                for playedNote in args
            )
        argumentString = self.argumentDefinition.getArgumentSeperator().join(
            argumentGenerator
        )
        if replaceString:
            processedScript = self.script.replace(replaceString, argumentString)
        elif not argumentString.isspace():
            processedScript = f"{self.script} {argumentString}"
        else:
            processedScript = self.script
        self.runProcess(processedScript)

    def queueIfNumArgumentsAllowed(self, args):
        if not self.argumentDefinition:
            if len(args) == 0:
                self.queue(args)
            return
        if not self.argumentDefinition.numArgumentsAllowed(len(args)):
            return
        self.queue(args)

    def queue(self, args):
        self.lazyInitializeThread()
        self.invocationQueue.put(args)

    def __str__(self):
        argumentDefinitionSpecification = (
            f"{self.argumentDefinition} " if self.argumentDefinition else ""
        )
        interpreterSpecification = f'("{self.interpreter}")' if self.interpreter else ""
        flagsSpecification = (
            f"[{'|'.join(flag for flag in FLAGS if self.flags & FLAGS[flag])}]"
            if self.flags
            else ""
        )
        indentedScript = "\n".join("\t" + line for line in self.script.splitlines())
        scriptSpecification = f"{{\n{indentedScript}\n}}"
        return f"{argumentDefinitionSpecification}{interpreterSpecification}{flagsSpecification}→\n{scriptSpecification}"
