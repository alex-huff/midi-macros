import os
import sys
import ASPN
import Parser
from appdirs import user_config_dir
import mido


def executeMacros(macroTree, pressed):
    print(
        f'Evaluating pressed keys: {[ASPN.midiNoteToASPN(n) for n, _ in pressed]}')
    macroTree.executeMacros(pressed)


configDirPath = user_config_dir('MIDIMacros')

if (not os.path.exists(configDirPath)):
    print(f'Config directory {configDirPath} does not exist, creating it now.')
    os.makedirs(configDirPath)
elif (not os.path.isdir(configDirPath)):
    print(
        f'ERROR: Config directory {configDirPath} already exists as a file.', file=sys.stderr)
    sys.exit(-1)

macroFilePath = os.path.join(configDirPath, 'macros')

if (not os.path.exists(macroFilePath)):
    print(f'Macro file {macroFilePath} does not exist, creating it now.')
    open(macroFilePath, 'a').close()

with open(macroFilePath, 'r') as macroFile:
    macroTree = Parser.parseMacroFile(macroFile)

pressed = []
pedalDown = False
queuedReleases = set()
lastChangeWasAdd = False
midiDevice = 'Digital Piano MIDI 1'
inPort = mido.open_input(midiDevice)

for message in inPort:
    if (message.type != 'note_on' and message.type != 'note_off' and (message.type != 'control_change' or message.control != 64)):
        continue
    if (message.type == 'control_change'):
        if (message.value > 0):
            pedalDown = True
        else:
            pedalDown = False
            if (lastChangeWasAdd and len(queuedReleases) > 0):
                executeMacros(macroTree, pressed)
                lastChangeWasAdd = False
            pressed = [nv for nv in pressed if nv[0] not in queuedReleases]
            queuedReleases.clear()
        continue
    wasPress = message.type == 'note_on'
    note = message.note
    velocity = message.velocity
    if (wasPress):
        if (note in queuedReleases):
            queuedReleases.remove(note)
        pressed.append((note, velocity))
    else:
        if (pedalDown):
            queuedReleases.add(note)
            continue
        else:
            if (lastChangeWasAdd):
                executeMacros(macroTree, pressed)
            pressed = [nv for nv in pressed if nv[0] != note]
    lastChangeWasAdd = wasPress
