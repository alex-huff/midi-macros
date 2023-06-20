import sys
import re
import ASPN
from MacroTree import MacroTree


class ParseError(Exception):
    def __init__(self, message):
        self.message = message


lineContinuationRegex = re.compile(r'\\\s*\n')
pitchRegexString = r'[A-Ga-g]'
pitchRegex = re.compile(pitchRegexString)
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
            print(f'Adding macro {getPrettySequence(sequence)} -> {script}')
            macroTree.addSequenceToTree(sequence, script)
    return macroTree


def parseMacroFileLine(line):
    sequence, position = parseMacroDefinition(line, 0)
    while (position < len(line) and line[position].isspace()):
        position += 1
    script = parseScripts(line, position)
    return sequence, script


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
            line, position, f'(, *, {pitchRegexString} or [0-9]', 'EOL'))
    nextChar = line[position]
    if (nextChar == '('):
        return parseChord(line, position)
    if (nextChar.isdigit() or pitchRegex.match(nextChar) != None):
        return parseNote(line, position)
    if (nextChar == '*'):
        return -1, position + 1
    raise ParseError(generateParseErrorMessage(
        line, position, f'(, *, {pitchRegexString} or [0-9]', nextChar))


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
            line, position, f'{pitchRegexString} or [0-9]', 'EOL'))
    if (line[position].isdigit()):
        return parseMIDINote(line, position)
    elif (pitchRegex.match(line[position]) != None):
        return parseASPNNote(line, position)
    raise ParseError(generateParseErrorMessage(
        line, position, f'{pitchRegexString} or [0-9]', line[position]))


def parseMIDINote(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, '[0-9]', 'EOL'))
    startPosition = position
    while (position < len(line) and line[position].isdigit()):
        position += 1
    if (position == startPosition):
        raise ParseError(generateParseErrorMessage(
            line, position, '[0-9]', line[position]))
    return int(line[startPosition:position]), position


def parseASPNNote(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, f'{pitchRegexString}', 'EOL'))
    if (pitchRegex.match(line[position]) == None):
        raise ParseError(generateParseErrorMessage(
            line, position, f'{pitchRegexString}', line[position]))
    offset = 0
    basePitch = str.upper(line[position])
    position += 1
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, f'[{modifiers}], - or [0-9]', 'EOL'))
    if (line[position] in modifiers):
        offset, position = parseASPNModifiers(line, position)
    octave, position = parseASPNOctave(line, position)
    return ASPN.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset), position


def parseASPNOctave(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, '- or [0-9]', 'EOL'))
    modifier = 1
    if (line[position] == '-'):
        modifier = -1
        position += 1
    startPosition = position
    while (position < len(line) and line[position].isdigit()):
        position += 1
    if (position == startPosition):
        raise ParseError(generateParseErrorMessage(
            line, position, '[0-9]' if modifier == -1 else '- or [0-9]', 'EOL'))
    return modifier * int(line[startPosition:position]), position


def parseASPNModifiers(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, f'[{modifiers}]', 'EOL'))
    if (line[position] not in modifiers):
        raise ParseError(generateParseErrorMessage(
            line, position, f'[{modifiers}]', line[position]))
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


def parseScripts(line, position):
    if (position == len(line)):
        raise ParseError(generateParseErrorMessage(
            line, position, 'script', 'EOL'))
    return line[position:]
    # scriptString = os.path.expanduser(scriptString)
    # fileInPATH = shutil.which(scriptString)
    # scripts = [fileInPATH] if fileInPATH != None else glob(scriptString)
    # if (len(scripts) == 0):
    #     raise ParseError(f'Invalid script: {scriptString}.')
    # return scripts
