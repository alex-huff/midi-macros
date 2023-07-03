import os
import socket
import sys
import argparse
import stat
from rtmidi import MidiIn
from rtmidi._rtmidi import InvalidPortError
from appdirs import user_config_dir
from parser.parser import ParseError
from listener.midi_listener import MidiListener
from ipc.protocol import MessageFormatException, getIPCSocketPath, readMessage, sendString
from config.mm_config import SOCKET_PATH, PROFILES, MACRO_FILE, loadConfig, ConfigException


def verifyDirectoryExists(path, name):
    if (not os.path.exists(path)):
        print(f'INFO: {name} directory {path} does not exist, creating it now')
        os.makedirs(path)
    elif (not os.path.isdir(path)):
        print(
            f'ERROR: {name} directory {path} already exists as a file', file=sys.stderr)
        sys.exit(-1)


class ListMidiDevicesAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print('\n'.join(rtmidi.MidiIn().get_ports()))
        parser.exit()


class MidiMacros():
    def __init__(self, args):
        self.configDirPath = user_config_dir('midi-macros')
        self.macroDirPath = os.path.join(self.configDirPath, 'macros')
        verifyDirectoryExists(self.configDirPath, 'config')
        verifyDirectoryExists(self.macroDirPath, 'macro')
        if (args.config):
            self.configFilePath = args.config
        else:
            self.configFilePath = os.path.join(
                self.configDirPath, 'midi-macros.toml')
            if (not os.path.exists(self.configFilePath)):
                print(
                    f'Config file {self.configFilePath} does not exist, creating it now')
                open(self.configFilePath, 'a').close()
        self.initConfig()
        self.createListeners()

    def initConfig(self):
        if (not self.reloadConfig()):
            sys.exit(-1)

    def reloadConfig(self):
        try:
            self.config = loadConfig(self.configFilePath)
            self.fixMacroPaths()
            return True
        except ConfigException as configException:
            print(f'ERROR: {configException.message}', file=sys.stderr)
        except FileNotFoundError:
            print(
                f'ERROR: config file path: {self.configFilePath}, was not a valid file', file=sys.stderr)
        except PermissionError:
            print(
                f'ERROR: insufficient permissions to open config file: {self.configFilePath}', file=sys.stderr)
        except:
            print(
                f'ERROR: failed to open config file: {self.configFilePath}', file=sys.stderr)
        return False

    def fixMacroPaths(self):
        for profileConfig in self.config[PROFILES].values():
            givenMacroFilePath = os.path.expanduser(profileConfig[MACRO_FILE])
            if (os.path.isabs(givenMacroFilePath)):
                profileConfig[MACRO_FILE] = givenMacroFilePath
            else:
                profileConfig[MACRO_FILE] = os.path.join(
                    self.macroDirPath, givenMacroFilePath)

    def createListeners(self):
        self.listeners = {}
        for profileName, profileConfig in self.config[PROFILES].items():
            listener = MidiListener(profileName, profileConfig)
            self.listeners[profileName] = listener
            self.tryRunListener(profileName)

    def tryRunListener(self, profileName):
        try:
            self.listeners[profileName].run()
        except ParseError as parseError:
            print(f'ERROR: {parseError.message}', file=sys.stderr)
        except InvalidPortError:
            print(f'ERROR: profile: {profileName}, has invalid midi port', file=sys.stderr)
        except (FileNotFoundError, IsADirectoryError):
            print(f'ERROR: profile: {profileName}, has invalid macro file', file=sys.stderr)
        except PermissionError:
            print(f'ERROR: could not open macro file for profile: {profileName}', file=sys.stderr)
        except Exception as exception:
            exceptionMessage = getattr(exception, 'message', repr(exception))
            print(f'ERROR: failed to start midi listener for profile: {profileName}, {exceptionMessage}', file=sys.stderr)

    def startServer(self):
        self.ipcServer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if (SOCKET_PATH in self.config):
            self.unixSocketPath = self.config[SOCKET_PATH]
        else:
            self.unixSocketPath = getIPCSocketPath()
        self.unlinkExistingSocket()
        self.bindServer()
        while (True):
            ipcSocket, _ = self.ipcServer.accept()
            ipcSocket.settimeout(10)
            try:
                message = readMessage(ipcSocket)
                print(message)
                # response = handleMessage(message)
                sendString(ipcSocket, 'placeholder response')
            except MessageFormatException as messageFormatException:
                print(f'ERROR: {messageFormatException.message}',
                      file=sys.stderr)
            except Exception as exception:
                print(getattr(exception, 'message', repr(exception)))
            finally:
                ipcSocket.close()

    def unlinkExistingSocket(self):
        try:
            mode = os.stat(self.unixSocketPath).st_mode
            if (not stat.S_ISSOCK(mode)):
                print(
                    f'ERROR: file: {self.unixSocketPath}, exists and is not a socket', file=sys.stderr)
                sys.exit(-1)
            os.unlink(self.unixSocketPath)
        except FileNotFoundError:
            pass
        except Exception as exception:
            exceptionMessage = getattr(exception, 'message', repr(exception))
            print(
                f'ERROR: could not unlink socket file: {self.unixSocketPath}, {exceptionMessage}', file=sys.stderr)
            sys.exit(-1)

    def bindServer(self):
        try:
            self.ipcServer.bind(self.unixSocketPath)
        except Exception as exception:
            exceptionMessage = getattr(exception, 'message', repr(exception))
            print(
                f'ERROR: could not bind to socket file: {self.unixSocketPath}, {exceptionMessage}', file=sys.stderr)
            sys.exit(-1)
        print(f'Listening on socket: {self.unixSocketPath}')
        self.ipcServer.listen(1)


PROGRAM_NAME = 'midi-macros'
VERSION = f'{PROGRAM_NAME} 0.0.1'
parser = argparse.ArgumentParser(
    prog=PROGRAM_NAME,
    description='Execute scripts with your MIDI instrument'
)
parser.add_argument('-v', '--version', action='version',
                    version=VERSION, help='show version number and exit')
parser.add_argument('--list-midi-devices', action=ListMidiDevicesAction,
                    nargs=0, help='list connected MIDI device names')
parser.add_argument(
    '-c', '--config', help='use alternative configuration file')
args = parser.parse_args()

midiMacros = MidiMacros(args)
try:
    midiMacros.startServer()
except KeyboardInterrupt:
    pass
finally:
    midiMacros.unlinkExistingSocket()
