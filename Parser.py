import sys
import re
import math
import ASPN
from MacroArgument import MacroArgumentDefinition, MacroArgumentFormat, MacroArgumentNumberRange, UNBOUNDED_MANR
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
argumentFormatShorthands = 'mpaAv'
argumentFormatShorthandToMAF = {
    'm': MacroArgumentFormat.MIDI,
    'p': MacroArgumentFormat.PIANO,
    'a': MacroArgumentFormat.ASPN,
    'A': MacroArgumentFormat.ASPN_UNICODE,
    'v': MacroArgumentFormat.VELOCITY,
}


def generateParseError(line, position, expected, got):
    arrowLine = ' ' * position + '^'
    expectedString = f'Expected: {expected}\n' if expected else ''
    gotString = f'Got: {got}\n' if got else ''
    raise ParseError(
        f'\n{expectedString}{gotString}While parsing:\n{line}\n{arrowLine}')


def generateInvalidMIDIError(line, position, note):
    arrowLine = ' ' * position + '^'
    raise ParseError(f'\nInvalid MIDI note: {note}\n{line}\n{arrowLine}')


def getPrettyNoteString(note):
    matchPredicateString = f'({note[1]})' if note[1] != 'True' else ''
    return f'{ASPN.midiNoteToASPN(note[0])}{matchPredicateString}'


def getPrettySequenceString(sequence):
    prettySequence = []
    for subSequence in sequence:
        match (subSequence):
            case (MacroArgumentDefinition()):
                prettySequence.append(subSequence.__str__())
            case (tuple()):
                if (isinstance(subSequence[0], tuple)):
                    prettySequence.append(
                        f'({"|".join((getPrettyNoteString(n) for n in subSequence))})')
                else:
                    prettySequence.append(getPrettyNoteString(subSequence))
    return '+'.join(prettySequence)


def preprocessFile(macroFile):
    return lineContinuationRegex.sub('', macroFile.read())


def validateMacroSequence(sequence):
    for subSequence in (subSequence for i, subSequence in enumerate(sequence) if isinstance(subSequence, MacroArgumentDefinition) and i < len(sequence) - 1):
        print(
            f'ERROR: Argument definition: {subSequence} found before end of macro', file=sys.stderr)
        sys.exit(-1)


def parseMacroFile(macroFile):
    macroTree = MacroTree()
    processedText = preprocessFile(macroFile)
    for line in processedText.split('\n'):
        if (len(line) == 0 or str.isspace(line)):
            continue
        line = ParseBuffer(line)
        position = 0
        position = eatWhitespace(line, position)
        if (line[position] == '#'):
            continue
        try:
            sequence, script = parseMacroFileLine(line, position)
        except ParseError as pe:
            print(f'Parsing ERROR: {pe.message}', file=sys.stderr)
            sys.exit(-1)
        validateMacroSequence(sequence)
        print(
            f'Adding macro {getPrettySequenceString(sequence)} → {script}')
        macroTree.addSequenceToTree(sequence, script)
    return macroTree


def eatWhitespace(line, position):
    while (line[position].isspace()):
        position += 1
    return position


def parseMacroFileLine(line, position):
    sequence, position = parseMacroDefinition(line, position)
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
        position = eatWhitespace(line, position)
        subSequence, position = parseSubMacro(line, position)
        sequence.append(subSequence)
        position = eatWhitespace(line, position)
        if (line[position] != '+'):
            return sequence, position
        position += 1


def parseSubMacro(line, position):
    nextChar = line[position]
    if (nextChar == '('):
        return parseChord(line, position)
    if (nextChar.isdigit() or basePitchRegex.match(nextChar)):
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
        position = eatWhitespace(line, position)
        note, position = parseNote(line, position)
        chord.append(note)
        position = eatWhitespace(line, position)
        if (line[position] not in '|)'):
            generateParseError(
                line, position, '| or )', line[position])
        if (line[position] == ')'):
            chord.sort(key=lambda n: n[0])
            return tuple(chord), position + 1
        position += 1


def inMidiRange(note):
    return note >= 0 and note <= 127


def parseNote(line, position):
    if (not line[position].isdigit() and not basePitchRegex.match(line[position])):
        generateParseError(
            line, position, 'note', line[position])
    startPosition = position
    if (line[position].isdigit()):
        note, position = parsePositiveInteger(line, position)
    else:
        note, position = parseASPNNote(line, position)
    if (not inMidiRange(note)):
        generateInvalidMIDIError(line, startPosition, note)
    matchPredicate = 'True'
    if (line[position] == '('):
        matchPredicate, position = parseMatchPredicate(line, position)
    return (note, matchPredicate), position


def parseASPNNote(line, position):
    if (not basePitchRegex.match(line[position])):
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
    unmodifiedNumber, position = parsePositiveInteger(line, position)
    return modifier * unmodifiedNumber, position


def parseASPNModifiers(line, position):
    if (line[position] not in modifiers):
        generateParseError(
            line, position, f'pitch modifiers ({modifiers})', line[position])
    offset = 0
    while True:
        match (line[position]):
            case ('#' | '♯'):
                offset += 1
            case ('b' | '♭'):
                offset -= 1
            case ('𝄪'):
                offset += 2
            case ('𝄫'):
                offset -= 2
            case (_):
                break
        position += 1
    return offset, position


def parseMatchPredicate(line, position):
    if (line[position] != '('):
        generateParseError(
            line, position, 'match predicate', line[position])
    position += 1
    startPosition = position
    numOpenParens = 0
    while (numOpenParens > 0 or line[position] != ')'):
        match (line[position]):
            case ('('):
                numOpenParens += 1
            case (')'):
                numOpenParens -= 1
            case ('"' | "'"):
                position = eatPythonString(line, position) - 1
        if (numOpenParens < 0):
            generateParseError(line, position, None, 'unmatched parenthesis')
        position += 1
    if (startPosition == position):
        generateParseError(line, position, None, 'empty match predicate')
    matchPredicate = line[startPosition:position].strip()
    return matchPredicate, position + 1


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
    if (line[position] != '*'):
        generateParseError(line, position, '*', line[position])
    position += 1
    if (line[position] not in '(['):
        generateParseError(
            line, position, 'argument number range or argument definition body', line[position])
    argumentNumberRange = UNBOUNDED_MANR
    if (line[position] == '['):
        argumentNumberRange, position = parseArgumentNumberRange(
            line, position)
    argumentDefinition, position = parseArgumentDefinitionBody(line, position)
    argumentDefinition.setArgumentNumberRange(argumentNumberRange)
    return argumentDefinition, position


def parseArgumentNumberRange(line, position):
    if (line[position] != '['):
        generateParseError(
            line, position, 'argument number range', line[position])
    position += 1
    lowerBound = 0
    setLowerBound = False
    if (line[position].isdigit()):
        lowerBound, position = parsePositiveInteger(line, position)
        setLowerBound = True
        if (line[position] == ']'):
            return MacroArgumentNumberRange(lowerBound, lowerBound), position + 1
    if (line[position] != ':'):
        generateParseError(
            line, position, 'number, : or ]' if setLowerBound else 'number, :', line[position])
    position += 1
    upperBound = math.inf
    if (line[position].isdigit()):
        upperBound, position = parsePositiveInteger(line, position)
    if (line[position] != ']'):
        generateParseError(line, position, 'number or ]', line[position])
    position += 1
    return MacroArgumentNumberRange(lowerBound, upperBound), position


def parsePositiveInteger(line, position):
    if (not line[position].isdigit()):
        generateParseError(line, position, 'positive number', line[position])
    startPosition = position
    while (line[position].isdigit()):
        position += 1
    return int(line[startPosition:position]), position


def parseArgumentDefinitionBody(line, position):
    if (line[position] != '('):
        generateParseError(
            line, position, 'argument definition body', line[position])
    position += 1
    position = eatWhitespace(line, position)
    replaceString = None
    if (line[position] == '"'):
        replaceString, position = parseQuotedString(line, position)
        replaceString = replaceString if replaceString else None
        position = eatWhitespace(line, position)
        position = parseArrow(line, position)
        position = eatWhitespace(line, position)
    if (line[position] == 'f'):
        argumentFormat, position = parseFStringArgumentFormat(line, position)
    else:
        argumentFormat, position = parseArgumentFormat(line, position)
    position = eatWhitespace(line, position)
    if (line[position] != ')'):
        generateParseError(line, position, ')', line[position])
    return MacroArgumentDefinition(argumentFormat, replaceString), position + 1


def parseQuotedString(line, position, quoteChar='"'):
    rawString, line = readQuotedString(line, position, quoteChar)
    try:
        decodedString = decodeCStyleEscapes(rawString)
    except UnicodeDecodeError as ude:
        raise ParseError(f'Failed to decode string: {rawString}, {ude.reason}')
    return decodedString, line


def readQuotedString(line, position, quoteChar='"'):
    if (line[position] != quoteChar):
        generateParseError(
            line, position, f'{quoteChar}-quoted string', line[position])
    position += 1
    startPosition = position
    escaping = False
    while (True):
        currentChar = line[position]
        if (currentChar == quoteChar and not escaping):
            break
        escaping = not escaping if currentChar == '\\' else False
        position += 1
    return line[startPosition:position], position + 1


def bufferHasSubstringAtPosition(line, position, substring):
    for i in range(len(substring)):
        if (position + i >= len(line) or line[position + i] != substring[i]):
            return False
    return True


def eatPythonString(line, position):
    if (line[position] not in '"\''):
        generateParseError(line, position, 'python string', line[position])
    quoteChar = line[position]
    isDocstring = bufferHasSubstringAtPosition(line, position, quoteChar * 3)
    position += 3 if isDocstring else 1
    escaping = False
    consecutiveUnescapedQuotes = 0
    while (True):
        currentChar = line[position]
        if (currentChar == quoteChar and not escaping):
            if (not isDocstring or consecutiveUnescapedQuotes == 2):
                break
            consecutiveUnescapedQuotes += 1
        else:
            consecutiveUnescapedQuotes = 0
        escaping = not escaping if currentChar == '\\' else False
        position += 1
    return position + 1


def decodeCStyleEscapes(string):
    return string.encode('latin1', 'backslashreplace').decode('unicode-escape')


def parseArgumentFormat(line, position):
    formatString, position = parseOneOfExpectedStrings(
        line, position, [f.name for f in MacroArgumentFormat])
    return MacroArgumentFormat.__members__[formatString], position


def parseFStringArgumentFormat(line, position):
    if (line[position] != 'f'):
        generateParseError(
            line, position, 'f-string argument format', line[position])
    position += 1
    fString, position = parseQuotedString(line, position)
    argumentFormat = []
    stringBuilder = []
    escaping = False
    currentStringStart = 0

    def addStringBuilderToArgumentFormat():
        if (len(stringBuilder) == 0):
            return
        argumentFormat.append(''.join(stringBuilder))
        stringBuilder.clear()

    def addToStringBuilder(end=None):
        if (currentStringStart != len(fString)):
            stringBuilder.append(fString[currentStringStart:end])

    for i, char in enumerate(fString):
        if (escaping and char == '%'):
            addToStringBuilder(i)
            currentStringStart = i + 1
        elif (escaping and char in argumentFormatShorthands):
            macroArgumentFormat = argumentFormatShorthandToMAF[char]
            if (i - 1 > currentStringStart):
                addToStringBuilder(i - 1)
                addStringBuilderToArgumentFormat()
            argumentFormat.append(macroArgumentFormat)
            currentStringStart = i + 1
        escaping = not escaping if char == '%' else False
    addToStringBuilder()
    addStringBuilderToArgumentFormat()
    return argumentFormat, position


def parseScripts(line, position):
    return line[position:]
