import re
import math
from log.mm_logging import logInfo
from aspn import aspn
from macro.macro_argument import *
from macro.tree.macro_tree import MacroTree
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.macro import Macro


class ParseError(Exception):
    def __init__(self, message):
        self.message = message


class ParseBuffer(str):
    def __getitem__(self, key):
        try:
            return ParseBuffer(str.__getitem__(self, key))
        except IndexError:
            raise ParseError(
                f'unexpectedly reached end of line.\n{self}\n{" " * len(self) + "^"}'
            )


LINE_CONTINUATION_REGEX = re.compile(r"\\\s*\n")
ARROW_START_CHARS = "→-"
BASE_PITCH_REGEX = re.compile(r"[A-Ga-g]")
MODIFIERS = "#♯b♭𝄪𝄫"
ARGUMENT_FORMAT_SHORTHANDS = "mpaAvt"
ARGUMENT_FORMAT_SHORTHANDS_TO_AF = {
    "m": FORMAT_MIDI,
    "p": FORMAT_PIANO,
    "a": FORMAT_ASPN,
    "A": FORMAT_ASPN_UNICODE,
    "v": FORMAT_VELOCITY,
    "t": FORMAT_TIME,
}


def generateParseError(line, position, expected, got):
    arrowLine = " " * position + "^"
    expectedString = f"expected: {expected}\n" if expected else ""
    gotString = f"got: {got}\n" if got else ""
    raise ParseError(
        f"\n{expectedString}{gotString}while parsing:\n{line}\n{arrowLine}"
    )


def generateInvalidMIDIError(line, position, note):
    arrowLine = " " * position + "^"
    raise ParseError(f"\ninvalid MIDI note: {note}\n{line}\n{arrowLine}")


def preprocessFile(macroFile):
    return LINE_CONTINUATION_REGEX.sub("", macroFile.read())


def parseMacroFile(macroFile, profile, subprofile=None):
    macroTree = MacroTree()
    processedText = preprocessFile(macroFile)
    for line in processedText.split("\n"):
        if len(line) == 0 or str.isspace(line):
            continue
        line = ParseBuffer(line)
        position = 0
        position = eatWhitespace(line, position)
        if line[position] == "#":
            continue
        macro, script = parseMacroFileLine(line, position)
        logInfo(f"adding macro: {macro} → {script}", profile, subprofile)
        macroTree.addMacroToTree(macro, script)
    return macroTree


def eatWhitespace(line, position):
    while position < len(line) and line[position].isspace():
        position += 1
    return position


def parseMacroFileLine(line, position):
    triggers, position = parseTriggers(line, position)
    position = eatWhitespace(line, position)
    if line[position] != "*" and line[position] not in ARROW_START_CHARS:
        generateParseError(
            line,
            position,
            "+, argument definition, or arrow operator (->, →)",
            line[position],
        )
    argumentDefinition = ZERO_ARGUMENT_DEFINITION
    if line[position] == "*":
        argumentDefinition, position = parseArgumentDefinition(line, position)
    position = eatWhitespace(line, position)
    position = parseArrow(line, position)
    position = eatWhitespace(line, position)
    script = parseScripts(line, position)
    return Macro(triggers, argumentDefinition), script


def parseArrow(line, position):
    if line[position] not in ARROW_START_CHARS:
        generateParseError(line, position, f"arrow operator (->, →)", line[position])
    if line[position] == "→":
        return position + 1
    position += 1
    if line[position] != ">":
        generateParseError(line, position, ">", line[position])
    return position + 1


def parseTriggers(line, position):
    triggers = []
    while True:
        position = eatWhitespace(line, position)
        subMacro, position = parseSubMacro(line, position)
        triggers.append(subMacro)
        position = eatWhitespace(line, position)
        if position == len(line) or line[position] != "+":
            return triggers, position
        position += 1


def parseSubMacro(line, position):
    nextChar = line[position]
    if nextChar == "(":
        return parseChord(line, position)
    if nextChar.isdigit() or BASE_PITCH_REGEX.match(nextChar):
        return parseNote(line, position)
    generateParseError(line, position, "note or chord", nextChar)


def parseChord(line, position):
    if line[position] != "(":
        generateParseError(line, position, "chord", line[position])
    position += 1
    chord = []
    while True:
        position = eatWhitespace(line, position)
        note, position = parseNote(line, position)
        chord.append(note)
        position = eatWhitespace(line, position)
        if line[position] not in "|)":
            generateParseError(line, position, "| or )", line[position])
        if line[position] == ")":
            position += 1
            chord.sort(key=lambda macroNote: macroNote.getNote())
            matchPredicate = "True"
            if position < len(line) and line[position] == "{":
                matchPredicate, position = getMatchPredicate(line, position)
            return MacroChord(tuple(chord), matchPredicate), position
        position += 1


def inMidiRange(note):
    return note >= 0 and note <= 127


def parseNote(line, position):
    if not line[position].isdigit() and not BASE_PITCH_REGEX.match(line[position]):
        generateParseError(line, position, "note", line[position])
    startPosition = position
    if line[position].isdigit():
        note, position = parsePositiveInteger(line, position)
    else:
        note, position = parseASPNNote(line, position)
    if not inMidiRange(note):
        generateInvalidMIDIError(line, startPosition, note)
    matchPredicate = "True"
    if position < len(line) and line[position] == "{":
        matchPredicate, position = getMatchPredicate(line, position)
    return MacroNote(note, matchPredicate), position


def parseASPNNote(line, position):
    if not BASE_PITCH_REGEX.match(line[position]):
        generateParseError(line, position, "ASPN note", line[position])
    offset = 0
    basePitch = str.upper(line[position])
    position += 1
    if (
        line[position] not in MODIFIERS
        and line[position] != "-"
        and not line[position].isdigit()
    ):
        generateParseError(
            line, position, f"pitch modifiers ({MODIFIERS}) or octave", line[position]
        )
    if line[position] in MODIFIERS:
        offset, position = parseASPNModifiers(line, position)
    octave, position = parseASPNOctave(line, position)
    return aspn.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset), position


def parseASPNOctave(line, position):
    modifier = 1
    if line[position] == "-":
        modifier = -1
        position += 1
    unmodifiedNumber, position = parsePositiveInteger(line, position)
    return modifier * unmodifiedNumber, position


def parseASPNModifiers(line, position):
    if line[position] not in MODIFIERS:
        generateParseError(
            line, position, f"pitch modifiers ({MODIFIERS})", line[position]
        )
    offset = 0
    while True:
        match (line[position]):
            case ("#" | "♯"):
                offset += 1
            case ("b" | "♭"):
                offset -= 1
            case ("𝄪"):
                offset += 2
            case ("𝄫"):
                offset -= 2
            case (_):
                break
        position += 1
    return offset, position


def getMatchPredicate(line, position):
    if line[position] != "{":
        generateParseError(line, position, "match predicate", line[position])
    position += 1
    startPosition = position
    numUnmatchedOpenLeftCurlyBraces = 0
    while numUnmatchedOpenLeftCurlyBraces > 0 or line[position] != "}":
        match (line[position]):
            case ("{"):
                numUnmatchedOpenLeftCurlyBraces += 1
            case ("}"):
                numUnmatchedOpenLeftCurlyBraces -= 1
            case ('"' | "'"):
                position = eatPythonString(line, position) - 1
        if numUnmatchedOpenLeftCurlyBraces < 0:
            generateParseError(line, position, None, "unmatched curly brace")
        position += 1
    if startPosition == position:
        generateParseError(line, position, None, "empty match predicate")
    matchPredicate = line[startPosition:position].strip()
    return matchPredicate, position + 1


def parseExpectedString(line, position, expected):
    end = position + len(expected)
    actual = line[position:end]
    if actual != expected:
        generateParseError(line, position, expected, actual)
    return actual, end


def parseOneOfExpectedStrings(line, position, expectedStrings):
    for expected in expectedStrings:
        end = position + len(expected)
        if end >= len(line):
            continue
        actual = line[position:end]
        if actual == expected:
            return actual, end
    generateParseError(line, position, f'one of {"|".join(expectedStrings)}', None)


def parseArgumentDefinition(line, position):
    if line[position] != "*":
        generateParseError(line, position, "*", line[position])
    position += 1
    if line[position] not in "([":
        generateParseError(
            line,
            position,
            "argument number range or argument definition body",
            line[position],
        )
    argumentNumberRange = UNBOUNDED_MANR
    if line[position] == "[":
        argumentNumberRange, position = parseArgumentNumberRange(line, position)
    argumentDefinition, position = parseArgumentDefinitionBody(line, position)
    argumentDefinition.setArgumentNumberRange(argumentNumberRange)
    return argumentDefinition, position


def parseArgumentNumberRange(line, position):
    if line[position] != "[":
        generateParseError(line, position, "argument number range", line[position])
    position += 1
    lowerBound = 0
    setLowerBound = False
    if line[position].isdigit():
        lowerBound, position = parsePositiveInteger(line, position)
        setLowerBound = True
        if line[position] == "]":
            return MacroArgumentNumberRange(lowerBound, lowerBound), position + 1
    if line[position] != ":":
        generateParseError(
            line,
            position,
            "number, : or ]" if setLowerBound else "number, :",
            line[position],
        )
    position += 1
    upperBound = math.inf
    if line[position].isdigit():
        upperBound, position = parsePositiveInteger(line, position)
    if line[position] != "]":
        generateParseError(line, position, "number or ]", line[position])
    position += 1
    return MacroArgumentNumberRange(lowerBound, upperBound), position


def parsePositiveInteger(line, position):
    if not line[position].isdigit():
        generateParseError(line, position, "positive number", line[position])
    startPosition = position
    while position < len(line) and line[position].isdigit():
        position += 1
    return int(line[startPosition:position]), position


def parseArgumentDefinitionBody(line, position):
    if line[position] != "(":
        generateParseError(line, position, "argument definition body", line[position])
    position += 1
    position = eatWhitespace(line, position)
    replaceString = None
    if line[position] == '"':
        replaceString, position = parseQuotedString(line, position)
        replaceString = replaceString if replaceString else None
        position = eatWhitespace(line, position)
        position = parseArrow(line, position)
        position = eatWhitespace(line, position)
    if line[position] == "f":
        argumentFormat, position = parseFStringArgumentFormat(line, position)
    else:
        argumentFormat, position = parseArgumentFormat(line, position)
    position = eatWhitespace(line, position)
    if line[position] != ")":
        generateParseError(line, position, ")", line[position])
    return MacroArgumentDefinition(argumentFormat, replaceString), position + 1


def parseQuotedString(line, position, quoteChar='"'):
    rawString, line = readQuotedString(line, position, quoteChar)
    try:
        decodedString = decodeCStyleEscapes(rawString)
    except UnicodeDecodeError as ude:
        raise ParseError(f"failed to decode string: {rawString}, {ude.reason}")
    return decodedString, line


def readQuotedString(line, position, quoteChar='"'):
    if line[position] != quoteChar:
        generateParseError(line, position, f"{quoteChar}-quoted string", line[position])
    position += 1
    startPosition = position
    escaping = False
    while True:
        currentChar = line[position]
        if currentChar == quoteChar and not escaping:
            break
        escaping = not escaping if currentChar == "\\" else False
        position += 1
    return line[startPosition:position], position + 1


def bufferHasSubstringAtPosition(line, position, substring):
    for i in range(len(substring)):
        if position + i >= len(line) or line[position + i] != substring[i]:
            return False
    return True


def eatPythonString(line, position):
    if line[position] not in "\"'":
        generateParseError(line, position, "python string", line[position])
    quoteChar = line[position]
    isDocstring = bufferHasSubstringAtPosition(line, position, quoteChar * 3)
    position += 3 if isDocstring else 1
    escaping = False
    consecutiveUnescapedQuotes = 0
    while True:
        currentChar = line[position]
        if currentChar == quoteChar and not escaping:
            if not isDocstring or consecutiveUnescapedQuotes == 2:
                break
            consecutiveUnescapedQuotes += 1
        else:
            consecutiveUnescapedQuotes = 0
        escaping = not escaping if currentChar == "\\" else False
        position += 1
    return position + 1


def decodeCStyleEscapes(string):
    return string.encode("latin1", "backslashreplace").decode("unicode-escape")


def parseArgumentFormat(line, position):
    formatString, position = parseOneOfExpectedStrings(
        line, position, [n for n in FORMATS.keys()]
    )
    return FORMATS[formatString], position


def parseFStringArgumentFormat(line, position):
    if line[position] != "f":
        generateParseError(line, position, "f-string argument format", line[position])
    position += 1
    fString, position = parseQuotedString(line, position)
    argumentFormat = []
    stringBuilder = []
    escaping = False
    currentStringStart = 0

    def addStringBuilderToArgumentFormat():
        if len(stringBuilder) == 0:
            return
        argumentFormat.append("".join(stringBuilder))
        stringBuilder.clear()

    def addToStringBuilder(end=None):
        if currentStringStart != len(fString):
            stringBuilder.append(fString[currentStringStart:end])

    for i, char in enumerate(fString):
        if escaping and char == "%":
            addToStringBuilder(i)
            currentStringStart = i + 1
        elif escaping and char in ARGUMENT_FORMAT_SHORTHANDS:
            macroArgumentFormat = ARGUMENT_FORMAT_SHORTHANDS_TO_AF[char]
            if i - 1 > currentStringStart:
                addToStringBuilder(i - 1)
                addStringBuilderToArgumentFormat()
            argumentFormat.append(macroArgumentFormat)
            currentStringStart = i + 1
        escaping = not escaping if char == "%" else False
    addToStringBuilder()
    addStringBuilderToArgumentFormat()
    return argumentFormat, position


def parseScripts(line, position):
    return line[position:]
