import time
import sys
from rtmidi.midiutil import open_midiinput
from aspn import aspn
from parser import parser
from listener.played_note import PlayedNote
from midi.constants import *


class MidiListener():
    def __init__(self, config, name):
        self.config = config
        self.name = name

    def updateConfig(self, config):
        self.config = config

    def initState(self):
        self.macroFile = self.config['macro-file']
        if (not self.macroFile):
            print(
                f'ERROR: macro file not specified for profile: {self.name}', file=sys.stderr)
            sys.exit(-1)
        with open(self.macroFile, 'r') as configFile:
            self.macroTree = parser.parseMacroFile(configFile)
        self.pressed = []
        self.pedalDown = False
        self.queuedReleases = set()
        self.lastChangeWasAdd = False

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
        print(
            f'Evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in self.pressed]}')
        self.macroTree.executeMacros(self.pressed)

    def run(self):
        self.initState()
        midiin, _ = open_midiinput(self.config['midi-input'])
        midiin.set_callback(self)
        while (True):
            time.sleep(2**32)
        midiin.close_port()
        del midiin
