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
pitchRegex = re.compile(r'[A-Ga-g]')
modifiers = '#♯b♭𝄪𝄫'


def generateParseErrorMessage(line, position, expected, got):
    arrowLine = ' ' * position + '^'
    raise ParseError(
        f'\nExpected: {expected}\nGot: {got}\nWhile parsing:\n{line}\n{arrowLine}')


def getPrettySequence(sequence):
    prettySequence = []
    for subSequence in sequence:
        match subSequence:
            case tuple():
                prettySequence.append(
                    tuple([ASPN.midiNoteToASPN(n) for n in subSequence]))
            case int():
                prettySequence.append(ASPN.midiNoteToASPN(
                    subSequence) if subSequence != -1 else '*')
    return prettySequence


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
        if (sequence != None and script != None):
            print(f'Adding macro {getPrettySequence(sequence)} → {script}')
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
        raise ParseError(generateParseErrorMessage(
            line, position, 'arrow operator (->, →)', 'EOL' if atEndOfLine else line[position]))
    if (line[position] == '→'):
        return position + 1
    position += 1
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] != '>'):
        raise ParseError(generateParseErrorMessage(
            line, position, '>', 'EOL' if atEndOfLine else line[position]))
    return position + 1


def parseMacroDefinition(line, position):
    sequence = []
    while (True):
        subSequence, position = parseSubMacro(line, position)
        sequence.append(subSequence)
        if (position == len(line)):
            raise ParseError(generateParseErrorMessage(
                line, position, '+ or arrow operator (->, →)', 'EOL'))
        nextChar = line[position]
        if (nextChar.isspace() or nextChar in '→-'):
            return sequence, position
        if (nextChar == '+'):
            position += 1
        else:
            raise ParseError(generateParseErrorMessage(
                line, position, '+ or arrow operator (->, →)', nextChar))


def parseSubMacro(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'chord, note, or argument definition', 'EOL'))
    nextChar = line[position]
    if (nextChar == '('):
        return parseChord(line, position)
    if (nextChar.isdigit() or pitchRegex.match(nextChar) != None):
        return parseNote(line, position)
    if (nextChar == '*'):
        return parseArgumentDefinition(line, position)
    raise ParseError(generateParseErrorMessage(
        line, position, 'chord, note, or argument definition', nextChar))


def parseChord(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] != '('):
        raise ParseError(generateParseErrorMessage(
            line, position, 'chord', 'EOL' if atEndOfLine else line[position]))
    position += 1
    chord = []
    while (True):
        note, position = parseNote(line, position)
        chord.append(note)
        atEndOfLine = position == len(line)
        if (atEndOfLine or line[position] not in '-)'):
            raise ParseError(generateParseErrorMessage(
                line, position, '- or )', 'EOL' if atEndOfLine else line[position]))
        if (line[position] == ')'):
            chord.sort()
            return tuple(chord), position + 1
        else:
            position += 1


def parseNote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or (not line[position].isdigit() and pitchRegex.match(line[position]) == None)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'note', 'EOL' if atEndOfLine else line[position]))
    if (line[position].isdigit()):
        return parseMIDINote(line, position)
    return parseASPNNote(line, position)


def parseMIDINote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or not line[position].isdigit()):
        raise ParseError(generateParseErrorMessage(
            line, position, 'MIDI note', 'EOL' if atEndOfLine else line[position]))
    startPosition = position
    position += 1
    while (position < len(line) and line[position].isdigit()):
        position += 1
    return int(line[startPosition:position]), position


def parseASPNNote(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or pitchRegex.match(line[position]) == None):
        raise ParseError(generateParseErrorMessage(
            line, position, 'ASPN note', 'EOL' if atEndOfLine else line[position]))
    offset = 0
    basePitch = str.upper(line[position])
    position += 1
    atEndOfLine = position == len(line)
    if (atEndOfLine or (line[position] not in modifiers and line[position] != '-' and not line[position].isdigit())):
        raise ParseError(generateParseErrorMessage(
            line, position, f'pitch modifiers ({modifiers}) or octave', 'EOL' if atEndOfLine else line[position]))
    if (line[position] in modifiers):
        offset, position = parseASPNModifiers(line, position)
    octave, position = parseASPNOctave(line, position)
    return ASPN.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset), position


def parseASPNOctave(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'octave', 'EOL'))
    modifier = 1
    if (line[position] == '-'):
        modifier = -1
        position += 1
    startPosition = position
    while (position < len(line) and line[position].isdigit()):
        position += 1
    if (position == startPosition):
        raise ParseError(generateParseErrorMessage(
            line, position, 'number' if modifier == -1 else 'octave', 'EOL'))
    return modifier * int(line[startPosition:position]), position


def parseASPNModifiers(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] not in modifiers):
        raise ParseError(generateParseErrorMessage(
            line, position, f'pitch modifiers ({modifiers})', 'EOL' if atEndOfLine else line[position]))
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
        raise ParseError(generateParseErrorMessage(
            line, position, 'argument definition', 'EOL' if atEndOfLine else line[position]))
    position += 1
    argumentFormat, position = parseArgumentFormat(line, position)
    atEndOfLine = position == len(line)
    if (atEndOfLine):
        raise ParseError(generateParseErrorMessage(
            line, position, 'argument replace string, + or arrow operator (->, →)', 'EOL'))
    replaceString = None
    startPosition = position
    while (position < len(line) and not str.isspace(line[position]) and line[position] not in '→-'):
        position += 1
    if (position != startPosition):
        replaceString = line[startPosition:position]
    return MacroArgumentDefinition(argumentFormat, replaceString), position


def parseArgumentFormat(line, position):
    atEndOfLine = position == len(line)
    if (atEndOfLine or line[position] not in 'maMA'):
        raise ParseError(generateParseErrorMessage(
            line, position, 'argument format', 'EOL' if atEndOfLine else line[position]))
    argumentFormat = MacroArgumentFormat.MIDI
    if (line[position] in 'aA'):
        argumentFormat = MacroArgumentFormat.ASPN
    return argumentFormat, position + 1


def parseScripts(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'script', 'EOL'))
    return line[position:]
