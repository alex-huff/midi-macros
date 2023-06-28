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
        macroFile = config['macro-file']
        if (not macroFile):
            print(
                f'ERROR: macro file not specified for profile: {self.name}', file=sys.stderr)
            sys.exit(-1)
        with open(macroFile, 'r') as configFile:
            self.macroTree = parser.parseMacroFile(configFile)

    def executeMacros(self, pressed):
        print(
            f'Evaluating pressed keys: {[aspn.midiNoteToASPN(playedNote.getNote()) for playedNote in pressed]}')
        self.macroTree.executeMacros(pressed)

    def run(self):
        pressed = []
        pedalDown = False
        queuedReleases = set()
        lastChangeWasAdd = False
        inPort = mido.open_input(self.config['midi-input'])
        for message in inPort:
            if (message.type != 'note_on' and message.type != 'note_off' and (message.type != 'control_change' or message.control != 64)):
                continue
            if (message.type == 'control_change'):
                if (message.value > 0):
                    pedalDown = True
                else:
                    pedalDown = False
                    if (lastChangeWasAdd and len(queuedReleases) > 0):
                        self.executeMacros(pressed)
                        lastChangeWasAdd = False
                    pressed = [playedNote for playedNote in pressed if playedNote.getNote(
                    ) not in queuedReleases]
                    queuedReleases.clear()
                continue
            wasPress = message.type == 'note_on' and message.velocity > 0
            note = message.note
            velocity = message.velocity
            if (wasPress):
                if (note in queuedReleases):
                    queuedReleases.remove(note)
                pressed.append(PlayedNote(note, velocity, time.time_ns()))
            else:
                if (pedalDown):
                    queuedReleases.add(note)
                    continue
                else:
                    if (lastChangeWasAdd):
                        self.executeMacros(pressed)
                    pressed = [
                        playedNote for playedNote in pressed if playedNote.getNote() != note]
            lastChangeWasAdd = wasPress
