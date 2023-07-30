import os
import socket
import sys
import argparse
import stat
import subprocess
from queue import Queue, Empty
from threading import Thread
from collections import defaultdict
from rtmidi import MidiIn
from appdirs import user_config_dir
from parser.parser import (
    ParseBuffer,
    ParseError,
    parseMacroFile,
    parseTriggers,
)
from listener.midi_listener import ListenerException, MidiListener
from ipc.protocol import (
    IPCIOError,
    getIPCSocketPath,
    readMessage,
    sendResponse,
    sendResponse,
)
from ipc.handler import handleMessage
from config.mm_config import (
    SOCKET_PATH,
    PROFILES,
    SUBPROFILES,
    GLOBAL_MACROS,
    MACROS,
    TRIGGER_TYPES,
    DEBOUNCE_CALLBACKS,
    loadConfig,
    ConfigException,
)
from log.mm_logging import loggingContext, logInfo, logError, exceptionStr


def verifyDirectoryExists(path, name):
    if not os.path.exists(path):
        logInfo(f"{name} directory {path} does not exist, creating it now")
        os.makedirs(path)
    elif not os.path.isdir(path):
        logError(f"{name} directory {path} already exists as a file")
        sys.exit(-1)


class ListMidiDevicesAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print("\n".join(MidiIn().get_ports()))
        parser.exit()


class MidiMacros:
    def __init__(self, arguments):
        self.configDirPath = user_config_dir("midi-macros")
        self.macroDirPath = os.path.join(self.configDirPath, "macros")
        verifyDirectoryExists(self.configDirPath, "config")
        verifyDirectoryExists(self.macroDirPath, "macro")
        if arguments.config:
            self.configFilePath = arguments.config
        else:
            self.configFilePath = os.path.join(self.configDirPath, "midi-macros.toml")
            if not os.path.exists(self.configFilePath):
                logInfo(
                    f"Config file {self.configFilePath} does not exist, creating it now"
                )
                open(self.configFilePath, "a").close()
        self.initConfig()
        self.callbackQueue = Queue()
        self.callbackThread = Thread(target=self.executeCallbacksForever, daemon=True)
        self.callbackThread.start()
        self.initialize()

    def executeCallbacksForever(self):
        while True:
            callbacks = [self.callbackQueue.get()]
            try:
                while True:
                    callbacks.append(self.callbackQueue.get_nowait())
            except Empty:
                pass
            debouncedCallbacks = defaultdict(dict)
            profileConfigs = self.config[PROFILES]
            for callback in callbacks:
                profile = callback.getProfile()
                if profileConfigs[profile][DEBOUNCE_CALLBACKS]:
                    debouncedCallbacks[profile][callback.getCallbackType()] = callback
                else:
                    self.executeCallback(callback)
            for debouncedCallbacksForProfile in debouncedCallbacks.values():
                for callback in debouncedCallbacksForProfile.values():
                    self.executeCallback(callback)
            for _ in range(len(callbacks)):
                self.callbackQueue.task_done()

    def executeCallback(self, callback):
        try:
            subprocess.Popen(
                callback.getScript(),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                shell=True,
                start_new_session=True,
            ).communicate(callback.getMessage())
        except Exception as exception:
            with loggingContext(callback.getProfile()):
                logError(
                    f"failed to run callback, {exceptionStr(exception)}",
                )

    def initialize(self):
        self.createAndRunListeners()

    def shutdown(self):
        logInfo("stopping listeners")
        self.stopListeners()
        logInfo("waiting for callbacks to complete")
        self.callbackQueue.join()

    def reload(self):
        logInfo("shutting down profiles")
        self.shutdown()
        logInfo("reloading configuration")
        result = self.reloadConfig()
        logInfo("initializing midi listeners")
        self.initialize()
        logInfo("reload completed")
        return result

    def initConfig(self):
        if not self.reloadConfig():
            sys.exit(-1)

    def reloadConfig(self):
        try:
            tempConfig = loadConfig(self.configFilePath)
            self.fixMacroFilePaths(tempConfig)
            self.parseControlTriggers(tempConfig)
            self.buildMacroTrees(tempConfig)
            self.config = tempConfig
            return True
        except ConfigException as configException:
            with loggingContext(configException.profile, configException.subprofile):
                logError(configException.message)
        except (FileNotFoundError, IsADirectoryError):
            logError(f"config file path: {self.configFilePath}, was not a valid file")
        except PermissionError:
            logError(
                f"insufficient permissions to open config file: {self.configFilePath}"
            )
        except Exception as exception:
            logError(
                f"failed to open config file: {self.configFilePath}, {exceptionStr(exception)}"
            )
        return False

    def fixMacroFilePath(self, givenMacroFilePath):
        givenMacroFilePath = os.path.expanduser(givenMacroFilePath)
        if os.path.isabs(givenMacroFilePath):
            return givenMacroFilePath
        return os.path.join(self.macroDirPath, givenMacroFilePath)

    def fixMacroFilePaths(self, config):
        for profileConfig in config[PROFILES].values():
            givenMacroFilePath = profileConfig[GLOBAL_MACROS]
            profileConfig[GLOBAL_MACROS] = self.fixMacroFilePath(givenMacroFilePath)
            for subprofileConfig in profileConfig[SUBPROFILES].values():
                givenMacroFilePath = subprofileConfig[MACROS]
                subprofileConfig[MACROS] = self.fixMacroFilePath(givenMacroFilePath)

    def parseControlTrigger(self, config, triggerType, profile=None, subprofile=None):
        try:
            profileSpecifier = f"@{profile}" if profile else ""
            subprofileSpecifier = f"@{subprofile}" if subprofile else ""
            lines = config[triggerType].splitlines()
            parseBuffer = ParseBuffer(
                lines, f"{triggerType}{subprofileSpecifier}{profileSpecifier}"
            )
            parseBuffer.skipTillData()
            trigger = parseTriggers(parseBuffer)
            parseBuffer.skipTillData()
            if not parseBuffer.atEndOfBuffer():
                extraData = parseBuffer.stringFrom(parseBuffer.at(), None)
                raise ConfigException(
                    f"extraneous data in {triggerType}:\n{extraData}",
                    profile,
                    subprofile,
                )
            config[triggerType] = trigger
        except ParseError as parseError:
            raise ConfigException(
                f"{parseError.getSourceSpecifier()}\nfailed to parse {triggerType}:\n{parseError.message}",
                profile,
                subprofile,
            )

    def parseControlTriggers(self, config):
        for profile, profileConfig in config[PROFILES].items():
            for triggerType in TRIGGER_TYPES:
                if triggerType in profileConfig:
                    self.parseControlTrigger(profileConfig, triggerType, profile)

    def buildMacroTree(self, macroFilePath, profile, subprofile=None):
        try:
            with open(macroFilePath, "r") as macroFile:
                return parseMacroFile(
                    macroFile, os.path.basename(macroFilePath), profile, subprofile
                )
        except ParseError as parseError:
            raise ConfigException(
                f"{parseError.getSourceSpecifier()}\nfailed to parse macro tree:\n{parseError.message}",
                profile,
                subprofile,
            )
        except (FileNotFoundError, IsADirectoryError):
            raise ConfigException(
                f"invalid macro file: {macroFilePath}", profile, subprofile
            )
        except PermissionError:
            raise ConfigException(
                f"insufficient permissions to open macro file: {macroFilePath}",
                profile,
                subprofile,
            )
        except Exception as exception:
            raise ConfigException(
                f"could not open macro file: {macroFilePath}, {exceptionStr(exception)}",
                profile,
                subprofile,
            )

    def buildMacroTrees(self, config):
        for profile, profileConfig in config[PROFILES].items():
            macroFilePath = profileConfig[GLOBAL_MACROS]
            profileConfig[GLOBAL_MACROS] = self.buildMacroTree(macroFilePath, profile)
            for subprofile, subprofileConfig in profileConfig[SUBPROFILES].items():
                macroFilePath = subprofileConfig[MACROS]
                subprofileConfig[MACROS] = self.buildMacroTree(
                    macroFilePath, profile, subprofile
                )

    def stopListeners(self):
        for listener in self.listeners.values():
            listener.stop()

    def getProfile(self, profile):
        return self.listeners.get(profile)

    def createAndRunListeners(self):
        self.listeners = {}
        for profile, profileConfig in self.config[PROFILES].items():
            listener = MidiListener(profile, profileConfig, self.callbackQueue)
            self.listeners[profile] = listener
            self.tryRunListener(listener)

    def getLoadedProfiles(self):
        return self.listeners.keys()

    def tryRunListener(self, listener):
        try:
            listener.run()
        except ListenerException as listenerException:
            logError(listenerException.message)

    def startServer(self):
        self.ipcServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if SOCKET_PATH in self.config:
            self.unixSocketPath = self.config[SOCKET_PATH]
        else:
            self.unixSocketPath = getIPCSocketPath()
        self.unlinkExistingSocket()
        self.bindServer()
        while True:
            ipcSocket, _ = self.ipcServer.accept()
            ipcSocket.settimeout(10)
            self.tryHandleClient(ipcSocket)

    def unlinkExistingSocket(self):
        try:
            mode = os.stat(self.unixSocketPath).st_mode
            if not stat.S_ISSOCK(mode):
                logError(f"file: {self.unixSocketPath}, exists and is not a socket")
                sys.exit(-1)
            os.unlink(self.unixSocketPath)
        except FileNotFoundError:
            pass
        except Exception as exception:
            logError(
                f"could not unlink socket file: {self.unixSocketPath}, {exceptionStr(exception)}"
            )
            sys.exit(-1)

    def bindServer(self):
        try:
            self.ipcServer.bind(self.unixSocketPath)
        except Exception as exception:
            logError(
                f"could not bind to socket file: {self.unixSocketPath}, {exceptionStr(exception)}"
            )
            sys.exit(-1)
        logInfo(f"listening on socket: {self.unixSocketPath}")
        self.ipcServer.listen(1)

    def tryHandleClient(self, ipcSocket):
        try:
            message = readMessage(ipcSocket)
            response = handleMessage(message, self)
            sendResponse(ipcSocket, response)
        except IPCIOError as exception:
            logError(exception.message)
        except Exception as exception:
            logError(f"failed to handle client, {exceptionStr(exception)}")
        finally:
            ipcSocket.close()


PROGRAM_NAME = "midi-macros"
VERSION = f"{PROGRAM_NAME} 0.0.1"
parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME, description="Execute scripts with your MIDI instrument"
)
parser.add_argument(
    "-v",
    "--version",
    action="version",
    version=VERSION,
    help="show version number and exit",
)
parser.add_argument(
    "--list-midi-devices",
    action=ListMidiDevicesAction,
    nargs=0,
    help="list connected MIDI device names",
)
parser.add_argument("-c", "--config", help="use alternative configuration file")
arguments = parser.parse_args()

midiMacros = MidiMacros(arguments)
try:
    midiMacros.startServer()
except KeyboardInterrupt:
    pass
finally:
    midiMacros.shutdown()
    midiMacros.unlinkExistingSocket()
