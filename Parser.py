import sys
import re
import ASPN
from MacroArgument import MacroArgumentFormat
from MacroArgument import MacroArgumentDefinition
from MacroTree import MacroTree


class ParseError(Exception):
    def __init__(self, message):
        self.message = message


lineContinuationRegex = re.compile(r'\\\s*\n')
basePitchRegex = re.compile(r'[A-Ga-g]')
modifiers = '#♯b♭𝄪𝄫'


def generateParseError(line, position, expected, got):
    arrowLine = ' ' * position + '^'
    raise ParseError(
        f'\nExpected: {expected}\nGot: {got}\nWhile parsing:\n{line}\n{arrowLine}')


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
        line = line.strip()
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
    while (position < len(line) and line[position].isspace()):
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
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] not in '→-'):
        generateParseError(
            line, position, 'arrow operator (->, →)', 'EOL' if atEndOfLine else line[position])
    if (line[position] == '→'):
        return position + 1
    position += 1
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] != '>'):
        generateParseError(
            line, position, '>', 'EOL' if atEndOfLine else line[position])
    return position + 1


def parseMacroDefinition(line, position):
    sequence = []
    while (True):
        subSequence, position = parseSubMacro(line, position)
        sequence.append(subSequence)
        if (position == len(line)):
            generateParseError(
                line, position, '+ or arrow operator (->, →)', 'EOL')
        nextChar = line[position]
        if (nextChar.isspace() or nextChar in '→-'):
            return sequence, position
        if (nextChar == '+'):
            position += 1
        else:
            generateParseError(
                line, position, '+ or arrow operator (->, →)', nextChar)


def parseSubMacro(line, position):
    if (position == len(line)):
        generateParseError(
            line, position, 'chord, note, or argument definition', 'EOL')
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
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] != '('):
        generateParseError(
            line, position, 'chord', 'EOL' if atEndOfLine else line[position])
    position += 1
    chord = []
    while (True):
        note, position = parseNote(line, position)
        chord.append(note)
        atEndOfLine = position == len(line)
        if (atEndOfLine or line[position] not in '|)'):
            generateParseError(
                line, position, '| or )', 'EOL' if atEndOfLine else line[position])
        if (line[position] == ')'):
            chord.sort()
            return tuple(chord), position + 1
        else:
            position += 1


def inMidiRange(note):
    return note >= 0 and note <= 127


def parseNote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or (not line[position].isdigit() and basePitchRegex.match(line[position]) == None)):
        generateParseError(
            line, position, 'note', 'EOL' if atEndOfLine else line[position])
    startPosition = position
    if (line[position].isdigit()):
        note, position = parseMIDINote(line, position)
    else:
        note, position = parseASPNNote(line, position)
    if (not inMidiRange(note)):
        generateInvalidMIDIError(line, startPosition, note)
    return note, position


def parseMIDINote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or not line[position].isdigit()):
        generateParseError(
            line, position, 'MIDI note', 'EOL' if atEndOfLine else line[position])
    startPosition = position
    position += 1
    while (position < len(line) and line[position].isdigit()):
        position += 1
    return int(line[startPosition:position]), position


def parseASPNNote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or basePitchRegex.match(line[position]) == None):
        generateParseError(
            line, position, 'ASPN note', 'EOL' if atEndOfLine else line[position])
    offset = 0
    basePitch = str.upper(line[position])
    position += 1
    atEndOfLine = position == len(line)
    if (atEndOfLine or (line[position] not in modifiers and line[position] != '-' and not line[position].isdigit())):
        generateParseError(
            line, position, f'pitch modifiers ({modifiers}) or octave', 'EOL' if atEndOfLine else line[position])
    if (line[position] in modifiers):
        offset, position = parseASPNModifiers(line, position)
    octave, position = parseASPNOctave(line, position)
    return ASPN.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset), position


def parseASPNOctave(line, position):
    if (position == len(line)):
        generateParseError(
            line, position, 'octave', 'EOL')
    modifier = 1
    if (line[position] == '-'):
        modifier = -1
        position += 1
    startPosition = position
    while (position < len(line) and line[position].isdigit()):
        position += 1
    if (position == startPosition):
        generateParseError(
            line, position, 'number' if modifier == -1 else 'octave', 'EOL')
    return modifier * int(line[startPosition:position]), position


def parseASPNModifiers(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] not in modifiers):
        generateParseError(
            line, position, f'pitch modifiers ({modifiers})', 'EOL' if atEndOfLine else line[position])
    offset = 0
    while position < len(line):
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


def parseArgumentDefinition(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] != '*'):
        generateParseError(
            line, position, 'argument definition', 'EOL' if atEndOfLine else line[position])
    position += 1
    argumentFormat, position = parseArgumentFormat(line, position)
    replaceString, position = parseReplaceString(line, position)
    return MacroArgumentDefinition(argumentFormat, replaceString), position


def parseReplaceString(line, position):
    replaceString = None
    startPosition = position
    while (position < len(line) and not str.isspace(line[position]) and line[position] not in '→-'):
        position += 1
    if (position != startPosition):
        replaceString = line[startPosition:position]
    return replaceString, position


def parseArgumentFormat(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] not in 'maAp'):
        generateParseError(
            line, position, 'argument format (m, a, A, or p)', 'EOL' if atEndOfLine else line[position])
    match line[position]:
        case 'a':
            argumentFormat = MacroArgumentFormat.ASPN
        case 'A':
            argumentFormat = MacroArgumentFormat.ASPN_UNICODE
        case 'p':
            argumentFormat = MacroArgumentFormat.PIANO
        case _:
            argumentFormat = MacroArgumentFormat.MIDI
    return argumentFormat, position + 1


def parseScripts(line, position):
    if (position == len(line)):
        generateParseError(
            line, position, 'script', 'EOL')
    return line[position:]
