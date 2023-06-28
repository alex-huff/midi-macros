import time
import sys
import mido
from aspn import aspn
from parser import parser
from listener.played_note import PlayedNote


class MidiListener():
    def __init__(self, config, name):
        self.config = config
        self.name = name
        self.pressed = []
        self.pedalDown = False
        self.queuedReleases = set()
        self.lastChangeWasAdd = False
        macroFile = config['macro-file']
        if (not macroFile):
            print(
                f'ERROR: macro file not specified for profile: {self.name}', file=sys.stderr)
            sys.exit(-1)
        with open(macroFile, 'r') as configFile:
            self.macroTree = parser.parseMacroFile(configFile)

    def executeMacros(self):
        print(
            f'Evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in self.pressed]}')
        self.macroTree.executeMacros(self.pressed)

    def run(self):
        inPort = mido.open_input(self.config['midi-input'])
        for message in inPort:
            if (message.type != 'note_on' and message.type != 'note_off' and (message.type != 'control_change' or message.control != 64)):
                continue
            if (message.type == 'control_change'):
                if (message.value > 0):
                    self.pedalDown = True
                else:
                    self.pedalDown = False
                    if (self.lastChangeWasAdd and len(self.queuedReleases) > 0):
                        self.executeMacros()
                        self.lastChangeWasAdd = False
                    self.pressed = [playedNote for playedNote in self.pressed if playedNote.getNote(
                    ) not in self.queuedReleases]
                    self.queuedReleases.clear()
                continue
            wasPress = message.type == 'note_on'
            note = message.note
            velocity = message.velocity
            if (wasPress):
                if (note in self.queuedReleases):
                    self.queuedReleases.remove(note)
                self.pressed.append(PlayedNote(note, velocity, time.time_ns()))
            else:
                if (self.pedalDown):
                    self.queuedReleases.add(note)
                    continue
                else:
                    if (self.lastChangeWasAdd):
                        self.executeMacros()
                    self.pressed = [
                        playedNote for playedNote in self.pressed if playedNote.getNote() != note]
            self.lastChangeWasAdd = wasPress
