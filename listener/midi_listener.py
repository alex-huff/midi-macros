import time
from rtmidi.midiutil import open_midiinput
from rtmidi._rtmidi import InvalidPortError, SystemError as RTMIDISystemError, NoDevicesError
from aspn import aspn
from log.mm_logging import logInfo
from parser.parser import ParseError, parseMacroFile
from listener.played_note import PlayedNote
from midi.constants import *
from config.mm_config import MACRO_FILE, MIDI_INPUT


class ListenerException(Exception):
    def __init__(self, message):
        self.message = message


class MidiListener():
    def __init__(self, profileName, config):
        self.profileName = profileName
        self.config = config

    def updateConfig(self, config):
        self.config = config

    def initialize(self):
        macroFilePath = self.config[MACRO_FILE]
        try:
            with open(macroFilePath, 'r') as macroFile:
                self.macroTree = parseMacroFile(macroFile, self.profileName)
            self.pressed = []
            self.pedalDown = False
            self.queuedReleases = set()
            self.lastChangeWasAdd = False
        except ParseError as parseError:
            raise ListenerException(parseError.message)
        except (FileNotFoundError, IsADirectoryError):
            raise ListenerException(f'invalid macro file: {macroFilePath}')
        except PermissionError:
            raise ListenerException(
                f'insufficient permissions to open macro file: {macroFilePath}')
        except Exception as exception:
            exceptionMessage = getattr(exception, 'message', repr(exception))
            raise ListenerException(
                f'could not open macro file: {macroFilePath}, {exceptionMessage}')

    def __call__(self, event, data=None):
        (status, data_1, data_2), _ = event
        if (status != NOTE_ON_STATUS and status != NOTE_OFF_STATUS and (status != CONTROL_CHANGE_STATUS or data_1 != SUSTAIN_PEDAL)):
            return
        if (status == CONTROL_CHANGE_STATUS):
            if (data_2 > 0):
                self.pedalDown = True
            else:
                self.pedalDown = False
                if (self.lastChangeWasAdd and len(self.queuedReleases) > 0):
                    self.executeMacros()
                    self.lastChangeWasAdd = False
                self.pressed = [playedNote for playedNote in self.pressed if playedNote.getNote(
                ) not in self.queuedReleases]
                self.queuedReleases.clear()
            return
        velocity = data_2
        note = data_1
        wasPress = status == NOTE_ON_STATUS and velocity > 0
        if (wasPress):
            if (note in self.queuedReleases):
                self.queuedReleases.remove(note)
            self.pressed.append(PlayedNote(note, velocity, time.time_ns()))
        else:
            if (self.pedalDown):
                self.queuedReleases.add(note)
                return
            else:
                if (self.lastChangeWasAdd):
                    self.executeMacros()
                self.pressed = [
                    playedNote for playedNote in self.pressed if playedNote.getNote() != note]
        self.lastChangeWasAdd = wasPress

    def executeMacros(self):
        logInfo(f'evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in self.pressed]}', self.profileName)
        self.macroTree.executeMacros(self.pressed)

    def run(self):
        self.initialize()
        self.openMIDIPort()

    def openMIDIPort(self):
        try:
            self.midiin, _ = open_midiinput(
                self.config[MIDI_INPUT], interactive=False)
            self.midiin.set_callback(self)
        except InvalidPortError:
            raise ListenerException(f'invalid midi port: {self.config[MIDI_INPUT]}')
        except RTMIDISystemError:
            raise ListenerException('MIDI system error')
        except NoDevicesError:
            raise ListenerException('no MIDI devices')

    def stop(self):
        # rtmidi internally will interrupt and join with callback thread
        if (not self.midiin):
            return
        self.midiin.close_port()
        del self.midiin
