import os
import sys
import subprocess
from glob import glob
from appdirs import user_config_dir
import mido


class ParseError(Exception):
    def __init__(self, message):
        self.message = message


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addSequenceToTree(self, sequence, scripts):
        if (len(sequence) == 0):
            return
        currentNode = self.root
        i = 0
        for i, trigger in enumerate(sequence):
            if (not currentNode.hasBranch(trigger)):
                break
            currentNode = currentNode.getBranch(trigger)
        else:
            currentNode.addScripts(scripts)
            return
        for trigger in sequence[i:]:
            if (trigger == -1):
                currentNode.setShouldPassExtraKeysAsArguments()
                break
            currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScripts(scripts)

    def executeMacros(self, pressed):
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, pressed)

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, pressed):
        keysLeftToProcess = len(pressed) - position
        if (keysLeftToProcess == 0):
            for script in currentNode.getScripts():
                subprocess.Popen(script)
            return
        if (currentNode.shouldPassExtraKeysAsArguments()):
            arguments = [str(note) for note in pressed[position:]]
            for script in currentNode.getScripts():
                command = [script]
                command.extend(arguments)
                subprocess.Popen(command)
        for trigger, nextNode in currentNode.getBranches().items():
            match trigger:
                case tuple():
                    chordLength = len(trigger)
                    if (chordLength <= keysLeftToProcess):
                        playedChord = pressed[position:position + chordLength]
                        playedChord.sort()
                        if (tuple(playedChord) == trigger):
                            self.recurseMacroTreeAndExecuteMacros(
                                nextNode, position + chordLength, pressed)
                case int():
                    if (pressed[position] == trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, pressed)


class MacroTreeNode:
    def __init__(self):
        self.branches = dict()
        self.scripts = []
        self.passExtraKeysAsArguments = False

    def setBranch(self, trigger, nextNode):
        self.branches[trigger] = nextNode
        return nextNode

    def hasBranch(self, trigger):
        return trigger in self.branches

    def getBranch(self, trigger):
        return self.branches[trigger]

    def getBranches(self):
        return self.branches

    def addScripts(self, scripts):
        self.scripts.extend(scripts)

    def getScripts(self):
        return self.scripts

    def setShouldPassExtraKeysAsArguments(self):
        self.passExtraKeysAsArguments = True

    def shouldPassExtraKeysAsArguments(self):
        return self.passExtraKeysAsArguments


def generateParseErrorMessage(line, position, expected, got):
    arrowLine = ' ' * position + '^'
    raise ParseError(
        f'Expected: {expected}, got: {got}.\nWhile parsing:\n{line},\n{arrowLine}')


def parseMacroFile(macroFile):
    macroTree = MacroTree()
    for line in macroFile.readlines():
        if (len(line) == 0 or str.isspace(line)):
            continue
        line = line.strip()
        try:
            sequence, scripts = parseMacroFileLine(line)
        except ParseError as pe:
            print(f'Parsing ERROR: {pe.message}', file=sys.stderr)
            sys.exit(-1)
        if (sequence != None and scripts != None):
            print(f'Adding macro {sequence} -> {scripts}')
            macroTree.addSequenceToTree(sequence, scripts)
    return macroTree


def parseMacroFileLine(line):
    sequence, position = parseMacroDefinition(line, 0)
    while (position < len(line) and line[position].isspace()):
        position += 1
    scripts = parseScripts(line, position)
    return sequence, scripts


def parseMacroDefinition(line, position):
    sequence = []
    while (True):
        subSequence, position = parseSubMacro(line, position)
        sequence.append(subSequence)
        if (position == len(line)):
            raise ParseError(generateParseErrorMessage(
                line, position, 'whitespace or +', 'EOL'))
        nextChar = line[position]
        if (nextChar.isspace()):
            return sequence, position
        if (nextChar == '+'):
            position += 1
        else:
            raise ParseError(generateParseErrorMessage(
                line, position, '+', nextChar))


def parseSubMacro(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, '( or [0-9]', 'EOL'))
    nextChar = line[position]
    if (nextChar == '('):
        return parseChord(line, position)
    if (nextChar.isdecimal()):
        return parseNote(line, position)
    if (nextChar == '*'):
        return -1, position + 1
    raise ParseError(generateParseErrorMessage(
        line, position, '(, * or [0-9]', nextChar))


def parseChord(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(line, position, '(', 'EOL'))
    if (line[position] != '('):
        raise ParseError(generateParseErrorMessage(
            line, position, '(', line[position]))
    position += 1
    chord = []
    while (True):
        note, position = parseNote(line, position)
        if (position == len(line)):
            raise ParseError(generateParseErrorMessage(
                line, position, ') or -', 'EOL'))
        chord.append(note)
        nextChar = line[position]
        if (nextChar == ')'):
            chord.sort()
            return tuple(chord), position + 1
        if (nextChar == '-'):
            position += 1
        else:
            raise ParseError(generateParseErrorMessage(
                line, position, '), or -', nextChar))


def parseNote(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, '[0-9]', 'EOL'))
    startPosition = position
    while (position < len(line) and line[position].isdigit()):
        position += 1
    return int(line[startPosition:position]), position


def parseScripts(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'script', 'EOL'))
    scriptString = line[position:]
    scripts = glob(os.path.expanduser(scriptString))
    if (len(scripts) == 0):
        raise ParseError(f'Invalid script: {scriptString}.')
    return scripts

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
    macroTree = parseMacroFile(macroFile)

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
                print(f'Evaluating pressed keys: {pressed}')
                macroTree.executeMacros(pressed)
                lastChangeWasAdd = False
            for toRelease in queuedReleases:
                pressed.remove(toRelease)
            queuedReleases.clear()
        continue
    wasPress = message.type == 'note_on'
    note = message.note
    if (wasPress):
        if (note in queuedReleases):
            queuedReleases.remove(note)
        if (note not in pressed):
            pressed.append(note)
        else:
            continue
    else:
        if (pedalDown):
            queuedReleases.add(note)
            continue
        else:
            if (lastChangeWasAdd):
                print(f'Evaluating pressed keys: {pressed}')
                macroTree.executeMacros(pressed)
            pressed.remove(note)
    lastChangeWasAdd = wasPress
