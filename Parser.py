import sys
import re
import ASPN
from MacroArgument import MacroArgumentFormat
from MacroArgument import MacroArgumentDefinition
from MacroTree import MacroTree


class ParseError(Exception):
    def __init__(self, message):
        self.message = message


class ParseBuffer(str):
    def __getitem__(self, key):
        try:
            return ParseBuffer(str.__getitem__(self, key))
        except IndexError:
            raise ParseError(
                f'Unexpectedly reached end of line.\n{self}\n{" " * len(self) + "^"}')


lineContinuationRegex = re.compile(r'\\\s*\n')
basePitchRegex = re.compile(r'[A-Ga-g]')
modifiers = '#♯b♭𝄪𝄫'


def generateParseError(line, position, expected, got):
    arrowLine = ' ' * position + '^'
    gotString = f'Got: {got}\n' if got != None else ''
    raise ParseError(
        f'\nExpected: {expected}\n{gotString}While parsing:\n{line}\n{arrowLine}')


def generateInvalidMIDIError(line, position, note):
    arrowLine = ' ' * position + '^'
    raise ParseError(f'\nInvalid MIDI note: {note}\n{line}\n{arrowLine}')


def getPrettySequenceString(sequence):
    prettySequence = []
    for subSequence in sequence:
        match subSequence:
            case MacroArgumentDefinition():
                prettySequence.append(subSequence.__str__())
            case tuple():
                prettySequence.append(
                    f'({"|".join([ASPN.midiNoteToASPN(n) for n in subSequence])})')
            case int():
                prettySequence.append(ASPN.midiNoteToASPN(subSequence))
    return '+'.join(prettySequence)


def preprocessFile(macroFile):
    fileString = macroFile.read()
    return lineContinuationRegex.sub('', fileString)


def parseMacroFile(macroFile):
    macroTree = MacroTree()
    processedText = preprocessFile(macroFile)
    for line in processedText.split('\n'):
        if (len(line) == 0 or str.isspace(line)):
            continue
        line = ParseBuffer(line.strip())
        try:
            sequence, script = parseMacroFileLine(line)
        except ParseError as pe:
            print(f'Parsing ERROR: {pe.message}', file=sys.stderr)
            sys.exit(-1)
        print(
            f'Adding macro {getPrettySequenceString(sequence)} → {script}')
        macroTree.addSequenceToTree(sequence, script)
    return macroTree


def eatWhitespace(line, position):
    while (line[position].isspace()):
        position += 1
    return position


def parseMacroFileLine(line):
    sequence, position = parseMacroDefinition(line, 0)
    position = eatWhitespace(line, position)
    position = parseArrow(line, position)
    position = eatWhitespace(line, position)
    script = parseScripts(line, position)
    return sequence, script


def parseArrow(line, position):
    if (line[position] not in '→-'):
        generateParseError(
            line, position, 'arrow operator (->, →)', line[position])
    if (line[position] == '→'):
        return position + 1
    position += 1
    if (line[position] != '>'):
        generateParseError(
            line, position, '>', line[position])
    return position + 1


def parseMacroDefinition(line, position):
    sequence = []
    while (True):
        subSequence, position = parseSubMacro(line, position)
        sequence.append(subSequence)
        nextChar = line[position]
        if (nextChar.isspace() or nextChar in '→-'):
            return sequence, position
        if (nextChar == '+'):
            position += 1
        else:
            generateParseError(
                line, position, '+ or arrow operator (->, →)', nextChar)


def parseSubMacro(line, position):
    nextChar = line[position]
    if (nextChar == '('):
        return parseChord(line, position)
    if (nextChar.isdigit() or basePitchRegex.match(nextChar) != None):
        return parseNote(line, position)
    if (nextChar == '*'):
        return parseArgumentDefinition(line, position)
    generateParseError(
        line, position, 'chord, note, or argument definition', nextChar)


def parseChord(line, position):
    if (line[position] != '('):
        generateParseError(
            line, position, 'chord', line[position])
    position += 1
    chord = []
    while (True):
        note, position = parseNote(line, position)
        chord.append(note)
        if (line[position] not in '|)'):
            generateParseError(
                line, position, '| or )', line[position])
        if (line[position] == ')'):
            chord.sort()
            return tuple(chord), position + 1
        else:
            position += 1


def inMidiRange(note):
    return note >= 0 and note <= 127


def parseNote(line, position):
    if (not line[position].isdigit() and basePitchRegex.match(line[position]) == None):
        generateParseError(
            line, position, 'note', line[position])
    startPosition = position
    if (line[position].isdigit()):
        note, position = parseMIDINote(line, position)
    else:
        note, position = parseASPNNote(line, position)
    if (not inMidiRange(note)):
        generateInvalidMIDIError(line, startPosition, note)
    return note, position


def parseMIDINote(line, position):
    if (not line[position].isdigit()):
        generateParseError(
            line, position, 'MIDI note', line[position])
    startPosition = position
    position += 1
    while (line[position].isdigit()):
        position += 1
    return int(line[startPosition:position]), position


def parseASPNNote(line, position):
    if (basePitchRegex.match(line[position]) == None):
        generateParseError(
            line, position, 'ASPN note', line[position])
    offset = 0
    basePitch = str.upper(line[position])
    position += 1
    if (line[position] not in modifiers and line[position] != '-' and not line[position].isdigit()):
        generateParseError(
            line, position, f'pitch modifiers ({modifiers}) or octave', line[position])
    if (line[position] in modifiers):
        offset, position = parseASPNModifiers(line, position)
    octave, position = parseASPNOctave(line, position)
    return ASPN.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset), position


def parseASPNOctave(line, position):
    modifier = 1
    if (line[position] == '-'):
        modifier = -1
        position += 1
    startPosition = position
    while (line[position].isdigit()):
        position += 1
    if (position == startPosition):
        generateParseError(
            line, position, 'number', line[position])
    return modifier * int(line[startPosition:position]), position


def parseASPNModifiers(line, position):
    if (line[position] not in modifiers):
        generateParseError(
            line, position, f'pitch modifiers ({modifiers})', line[position])
    offset = 0
    while True:
        match line[position]:
            case '#' | '♯':
                offset += 1
            case 'b' | '♭':
                offset -= 1
            case '𝄪':
                offset += 2
            case '𝄫':
                offset -= 2
            case _:
                break
        position += 1
    return offset, position


def parseExpectedString(line, position, expected):
    end = position + len(expected)
    actual = line[position:end]
    if (actual != expected):
        generateParseError(line, position, expected, actual)
    return actual, end


def parseOneOfExpectedStrings(line, position, expectedStrings):
    for expected in expectedStrings:
        end = position + len(expected)
        if (end >= len(line)):
            continue
        actual = line[position:end]
        if (actual == expected):
            return actual, end
    generateParseError(
        line, position, f'one of {"|".join(expectedStrings)}', None)


def parseArgumentDefinition(line, position):
    parseExpectedString(line, position, '*(')
    position += 2
    replaceString = None
    if (line[position] == '"'):
        replaceString, position = parseDoubleQuotedString(line, position)
        position = eatWhitespace(line, position)
        position = parseArrow(line, position)
        position = eatWhitespace(line, position)
    argumentFormat, position = parseArgumentFormat(line, position)
    if (line[position] != ')'):
        generateParseError(line, position, ')', line[position])
    return MacroArgumentDefinition(argumentFormat, replaceString), position + 1


def parseDoubleQuotedString(line, position):
    if (line[position] != '"'):
        generateParseError(
            line, position, 'double quoted string', line[position])
    position += 1
    startPosition = position
    while (line[position] != '"'):
        position += 1
    string = line[startPosition:position]
    return string, position + 1


def parseArgumentFormat(line, position):
    formatString, position = parseOneOfExpectedStrings(
        line, position, [f.name for f in MacroArgumentFormat])
    return MacroArgumentFormat.__members__[formatString], position


def parseScripts(line, position):
    return line[position:]
