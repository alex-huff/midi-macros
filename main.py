import os
import socket
import sys
import argparse
import stat
import subprocess
from queue import Queue, Empty
from threading import Thread, Event
from collections import defaultdict
from rtmidi import MidiIn
from appdirs import user_config_dir
from parser.parser import ParseBuffer, ParseError, eatWhitespace, parseTriggers
from listener.midi_listener import ListenerException, MidiListener
from ipc.protocol import (
    IPCIOError,
    MessageFormatException,
    getIPCSocketPath,
    readMessage,
    sendResponse,
    sendResponse,
)
from ipc.handler import handleMessage
from config.mm_config import (
    SOCKET_PATH,
    PROFILES,
    MACRO_FILE,
    TOGGLE_TRIGGER,
    DEBOUNCE_CALLBACKS,
    loadConfig,
    ConfigException,
)
from log.mm_logging import logInfo, logError, exceptionStr


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
    def __init__(self, args):
        self.configDirPath = user_config_dir("midi-macros")
        self.macroDirPath = os.path.join(self.configDirPath, "macros")
        verifyDirectoryExists(self.configDirPath, "config")
        verifyDirectoryExists(self.macroDirPath, "macro")
        if args.config:
            self.configFilePath = args.config
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
                profileName = callback.getProfileName()
                if profileConfigs[profileName][DEBOUNCE_CALLBACKS]:
                    debouncedCallbacks[profileName][callback.getCallbackType()] = callback
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
                start_new_session=True # so that KeyboardInterrupt does not SIGINT child process
            ).communicate(callback.getMessage())
        except Exception as exception:
            logError(
                f"failed to run callback, {exceptionStr(exception)}",
                callback.getProfileName(),
            )

    def initialize(self):
        self.createAndRunListeners()

    def shutdown(self):
        self.stopListeners()
        self.callbackQueue.join()

    def reload(self):
        self.shutdown()
        result = self.reloadConfig()
        self.initialize()
        return result

    def initConfig(self):
        if not self.reloadConfig():
            sys.exit(-1)

    def reloadConfig(self):
        try:
            tempConfig = loadConfig(self.configFilePath)
            self.fixMacroFilePaths(tempConfig)
            self.parseControlTriggers(tempConfig)
            self.config = tempConfig
            return True
        except ConfigException as configException:
            logError(configException.message, configException.profile)
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

    def fixMacroFilePaths(self, config):
        for profileConfig in config[PROFILES].values():
            givenMacroFilePath = os.path.expanduser(profileConfig[MACRO_FILE])
            if os.path.isabs(givenMacroFilePath):
                profileConfig[MACRO_FILE] = givenMacroFilePath
            else:
                profileConfig[MACRO_FILE] = os.path.join(
                    self.macroDirPath, givenMacroFilePath
                )

    def parseControlTrigger(self, profileName, profileConfig, triggerType):
        try:
            parseBuffer = ParseBuffer(profileConfig[triggerType])
            trigger, position = parseTriggers(parseBuffer, 0)
            position = eatWhitespace(parseBuffer, position)
            if position != len(parseBuffer):
                raise ConfigException(
                    f"extraneous characters in {triggerType}: {parseBuffer[position:]}"
                )
            profileConfig[triggerType] = trigger
        except ParseError as parseError:
            raise ConfigException(
                f"failed to parse {triggerType}: {parseError.message}", profileName
            )

    def parseControlTriggers(self, config):
        for profileName, profileConfig in config[PROFILES].items():
            if TOGGLE_TRIGGER in profileConfig:
                self.parseControlTrigger(profileName, profileConfig, TOGGLE_TRIGGER)

    def stopListeners(self):
        for listener in self.listeners.values():
            listener.stop()

    def getProfile(self, profileName):
        return self.listeners.get(profileName)

    def createAndRunListeners(self):
        self.listeners = {}
        for profileName, profileConfig in self.config[PROFILES].items():
            listener = MidiListener(profileName, profileConfig, self.callbackQueue)
            self.listeners[profileName] = listener
            self.tryRunListener(profileName)

    def getLoadedProfiles(self):
        return self.listeners.keys()

    def tryRunListener(self, profileName):
        try:
            self.listeners[profileName].run()
        except ListenerException as listenerException:
            logError(listenerException.message, profileName)

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
        except (MessageFormatException, IPCIOError) as exception:
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
args = parser.parse_args()

midiMacros = MidiMacros(args)
try:
    midiMacros.startServer()
except KeyboardInterrupt:
    pass
finally:
    midiMacros.shutdown()
    midiMacros.unlinkExistingSocket()
