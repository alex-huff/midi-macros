import re
import math
from log.mm_logging import logInfo
from aspn import aspn
from parser.parse_buffer import ParseBuffer
from parser.parse_error import ParseError
from macro.macro_argument import *
from macro.tree.macro_tree import MacroTree
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.macro import Macro


BASE_PITCH_REGEX = re.compile(r"[A-Ga-g]")
ARROW_START_CHARS = "→-"
MODIFIERS = "#♯b♭𝄪𝄫"
ARGUMENT_FORMAT_SHORTHANDS = "mpaAvt"
ARGUMENT_FORMAT_SHORTHANDS_TO_ARGUMENT_FORMAT = {
    "m": FORMAT_MIDI,
    "p": FORMAT_PIANO,
    "a": FORMAT_ASPN,
    "A": FORMAT_ASPN_UNICODE,
    "v": FORMAT_VELOCITY,
    "t": FORMAT_TIME,
}


def generateArrowLine(parseBuffer):
    return " " * parseBuffer.at()[1] + "^"


def generateParseError(parseBuffer, expected, got):
    expectedString = f"expected: {expected}\n" if expected else ""
    gotString = f"got: {got}\n" if got else ""
    raise ParseError(
        f"{expectedString}{gotString}while parsing:\n{parseBuffer}\n{generateArrowLine(parseBuffer)}",
        parseBuffer,
    )


def generateInvalidMIDIError(parseBuffer, note):
    raise ParseError(
        f"invalid MIDI note: {note}\n{parseBuffer}\n{generateArrowLine(parseBuffer)}",
        parseBuffer,
    )


def parseMacroFile(macroFile, source, profile, subprofile=None):
    macroTree = MacroTree()
    lines = [line[:-1] for line in macroFile.readlines()]
    if not lines:
        return macroTree
    parseBuffer = ParseBuffer(lines, source)
    while not parseBuffer.atEndOfBuffer():
        macro, script = parseMacroAndScript(parseBuffer)
        logInfo(f"adding macro: {macro} → {script}", profile, subprofile)
        macroTree.addMacroToTree(macro, script)
        parseBuffer.skipTillData()
    return macroTree


def parseMacroAndScript(parseBuffer):
    triggers = parseTriggers(parseBuffer)
    parseBuffer.skipTillData()
    if (
        parseBuffer.getCurrentChar() != "*"
        and parseBuffer.getCurrentChar() not in ARROW_START_CHARS
    ):
        generateParseError(
            parseBuffer,
            "+, argument definition, or arrow operator (->, →)",
            parseBuffer.getCurrentChar(),
        )
    argumentDefinition = ZERO_ARGUMENT_DEFINITION
    if parseBuffer.getCurrentChar() == "*":
        argumentDefinition = parseArgumentDefinition(parseBuffer)
    parseBuffer.skipTillData()
    eatArrow(parseBuffer)
    parseBuffer.skipTillData()
    script = parseScripts(parseBuffer)
    return Macro(triggers, argumentDefinition), script


def eatArrow(parseBuffer):
    if parseBuffer.getCurrentChar() not in ARROW_START_CHARS:
        generateParseError(
            parseBuffer, f"arrow operator (->, →)", parseBuffer.getCurrentChar()
        )
    if parseBuffer.getCurrentChar() == "→":
        parseBuffer.skip(1)
        return
    parseBuffer.skip(1)
    if parseBuffer.getCurrentChar() != ">":
        generateParseError(parseBuffer, ">", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)


def parseTriggers(parseBuffer):
    triggers = []
    while True:
        parseBuffer.skipTillData()
        subMacro = parseSubMacro(parseBuffer)
        triggers.append(subMacro)
        afterSubMacro = parseBuffer.at()
        parseBuffer.skipTillData()
        if parseBuffer.atEndOfLine() or parseBuffer.getCurrentChar() != "+":
            parseBuffer.jump(afterSubMacro)
            return triggers
        parseBuffer.skip(1)


def parseSubMacro(parseBuffer):
    if parseBuffer.getCurrentChar() == "(":
        return parseChord(parseBuffer)
    if parseBuffer.getCurrentChar().isdigit() or BASE_PITCH_REGEX.match(
        parseBuffer.getCurrentChar()
    ):
        return parseNote(parseBuffer)
    generateParseError(parseBuffer, "note or chord", parseBuffer.getCurrentChar())


def parseChord(parseBuffer):
    if parseBuffer.getCurrentChar() != "(":
        generateParseError(parseBuffer, "chord", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    chord = []
    while True:
        parseBuffer.skipTillData()
        note = parseNote(parseBuffer)
        chord.append(note)
        parseBuffer.skipTillData()
        if parseBuffer.getCurrentChar() not in "|)":
            generateParseError(parseBuffer, "| or )", parseBuffer.getCurrentChar())
        if parseBuffer.getCurrentChar() == ")":
            parseBuffer.skip(1)
            chord.sort(key=lambda macroNote: macroNote.getNote())
            matchPredicate = "True"
            if not parseBuffer.atEndOfLine() and parseBuffer.getCurrentChar() == "{":
                matchPredicate = parseMatchPredicate(parseBuffer)
            return MacroChord(tuple(chord), matchPredicate)
        parseBuffer.skip(1)


def inMidiRange(note):
    return note >= 0 and note <= 127


def parseNote(parseBuffer):
    if not parseBuffer.getCurrentChar().isdigit() and not BASE_PITCH_REGEX.match(
        parseBuffer.getCurrentChar()
    ):
        generateParseError(parseBuffer, "note", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    if parseBuffer.getCurrentChar().isdigit():
        note = parsePositiveInteger(parseBuffer)
    else:
        note = parseASPNNote(parseBuffer)
    if not inMidiRange(note):
        parseBuffer.jump(startPosition)
        generateInvalidMIDIError(parseBuffer, note)
    matchPredicate = "True"
    if not parseBuffer.atEndOfLine() and parseBuffer.getCurrentChar() == "{":
        matchPredicate = parseMatchPredicate(parseBuffer)
    return MacroNote(note, matchPredicate)


def parseASPNNote(parseBuffer):
    if not BASE_PITCH_REGEX.match(parseBuffer.getCurrentChar()):
        generateParseError(parseBuffer, "ASPN note", parseBuffer.getCurrentChar())
    offset = 0
    basePitch = str.upper(parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    if (
        parseBuffer.getCurrentChar() not in MODIFIERS
        and parseBuffer.getCurrentChar() != "-"
        and not parseBuffer.getCurrentChar().isdigit()
    ):
        generateParseError(
            parseBuffer,
            f"pitch modifiers ({MODIFIERS}) or octave",
            parseBuffer.getCurrentChar(),
        )
    if parseBuffer.getCurrentChar() in MODIFIERS:
        offset = parseASPNModifiers(parseBuffer)
    octave = parseASPNOctave(parseBuffer)
    return aspn.aspnOctaveBasePitchOffsetToMIDI(octave, basePitch, offset)


def parseASPNOctave(parseBuffer):
    modifier = 1
    if parseBuffer.getCurrentChar() == "-":
        modifier = -1
        parseBuffer.skip(1)
    unmodifiedNumber = parsePositiveInteger(parseBuffer)
    return modifier * unmodifiedNumber


def parseASPNModifiers(parseBuffer):
    if parseBuffer.getCurrentChar() not in MODIFIERS:
        generateParseError(
            parseBuffer,
            f"pitch modifiers ({MODIFIERS})",
            parseBuffer.getCurrentChar(),
        )
    offset = 0
    while True:
        match (parseBuffer.getCurrentChar()):
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
        parseBuffer.skip(1)
    return offset


def parseMatchPredicate(parseBuffer):
    if parseBuffer.getCurrentChar() != "{":
        generateParseError(parseBuffer, "match predicate", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    startPosition = parseBuffer.at()
    numUnmatchedOpenLeftCurlyBraces = 0
    while numUnmatchedOpenLeftCurlyBraces > 0 or parseBuffer.getCurrentChar() != "}":
        match (parseBuffer.getCurrentChar()):
            case ("{"):
                numUnmatchedOpenLeftCurlyBraces += 1
            case ("}"):
                numUnmatchedOpenLeftCurlyBraces -= 1
            case ('"' | "'"):
                eatPythonString(parseBuffer)
                continue
        if numUnmatchedOpenLeftCurlyBraces < 0:
            generateParseError(parseBuffer, None, "unmatched curly brace")
        parseBuffer.skip(1)
    endPosition = parseBuffer.at()
    if startPosition == endPosition:
        generateParseError(parseBuffer, None, "empty match predicate")
    matchPredicate = parseBuffer.stringFrom(startPosition, endPosition).strip()
    parseBuffer.skip(1)
    return matchPredicate


def parseOneOfExpectedStrings(parseBuffer, expectedStrings, otherExpected=None):
    for expected in expectedStrings:
        if bufferHasSubstring(parseBuffer, expected):
            parseBuffer.skip(len(expected))
            return expected
    otherExpectedSpecifier = f" or {otherExpected}" if otherExpected else ""
    generateParseError(
        parseBuffer, f'one of {"|".join(expectedStrings)}{otherExpectedSpecifier}', None
    )


def parseArgumentDefinition(parseBuffer):
    if parseBuffer.getCurrentChar() != "*":
        generateParseError(parseBuffer, "*", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    if parseBuffer.getCurrentChar() not in "([":
        generateParseError(
            parseBuffer,
            "argument number range or argument definition body",
            parseBuffer.getCurrentChar(),
        )
    argumentNumberRange = UNBOUNDED_MANR
    if parseBuffer.getCurrentChar() == "[":
        argumentNumberRange = parseArgumentNumberRange(parseBuffer)
    argumentDefinition = parseArgumentDefinitionBody(parseBuffer)
    argumentDefinition.setArgumentNumberRange(argumentNumberRange)
    return argumentDefinition


def parseArgumentNumberRange(parseBuffer):
    if parseBuffer.getCurrentChar() != "[":
        generateParseError(
            parseBuffer, "argument number range", parseBuffer.getCurrentChar()
        )
    parseBuffer.skip(1)
    lowerBound = 0
    setLowerBound = False
    if parseBuffer.getCurrentChar().isdigit():
        lowerBound = parsePositiveInteger(parseBuffer)
        setLowerBound = True
        if parseBuffer.getCurrentChar() == "]":
            parseBuffer.skip(1)
            return MacroArgumentNumberRange(lowerBound, lowerBound)
    if parseBuffer.getCurrentChar() != ":":
        generateParseError(
            parseBuffer,
            "number, : or ]" if setLowerBound else "number, :",
            parseBuffer.getCurrentChar(),
        )
    parseBuffer.skip(1)
    upperBound = math.inf
    if parseBuffer.getCurrentChar().isdigit():
        upperBound = parsePositiveInteger(parseBuffer)
    if parseBuffer.getCurrentChar() != "]":
        generateParseError(parseBuffer, "number or ]", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return MacroArgumentNumberRange(lowerBound, upperBound)


def parsePositiveInteger(parseBuffer):
    if not parseBuffer.getCurrentChar().isdigit():
        generateParseError(parseBuffer, "positive number", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    while not parseBuffer.atEndOfLine() and parseBuffer.getCurrentChar().isdigit():
        parseBuffer.skip(1)
    return int(parseBuffer.stringFrom(startPosition, parseBuffer.at()))


def parseArgumentDefinitionBody(parseBuffer):
    if parseBuffer.getCurrentChar() != "(":
        generateParseError(
            parseBuffer,
            "argument definition body",
            parseBuffer.getCurrentChar(),
        )
    parseBuffer.skip(1)
    replaceString = None
    if parseBuffer.getCurrentChar() == '"':
        replaceString = parseQuotedString(parseBuffer)
        replaceString = replaceString if replaceString else None
        eatArrow(parseBuffer)
    if parseBuffer.getCurrentChar() == "f":
        argumentFormat = parseFStringArgumentFormat(parseBuffer)
    else:
        argumentFormat = parseArgumentFormat(
            parseBuffer, otherExpected="f-string argument format or replace string"
        )
    if parseBuffer.getCurrentChar() != ")":
        generateParseError(parseBuffer, ")", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return MacroArgumentDefinition(argumentFormat, replaceString)


def parseQuotedString(parseBuffer, quoteChar='"'):
    stringStart = parseBuffer.at()
    rawString = readQuotedString(parseBuffer, quoteChar)
    try:
        return decodeCStyleEscapes(rawString)
    except UnicodeDecodeError as ude:
        parseBuffer.jump(stringStart)
        raise ParseError(
            f"failed to decode string: {rawString}, {ude.reason}", parseBuffer
        )


def readQuotedString(parseBuffer, quoteChar='"'):
    if parseBuffer.getCurrentChar() != quoteChar:
        generateParseError(
            parseBuffer, f"{quoteChar}-quoted string", parseBuffer.getCurrentChar()
        )
    parseBuffer.skip(1)
    startPosition = parseBuffer.at()
    escaping = False
    while True:
        if parseBuffer.getCurrentChar() == quoteChar and not escaping:
            break
        escaping = not escaping if parseBuffer.getCurrentChar() == "\\" else False
        parseBuffer.skip(1)
    endPosition = parseBuffer.at()
    parseBuffer.skip(1)
    return parseBuffer.stringFrom(startPosition, endPosition)


def bufferHasSubstring(parseBuffer, substring):
    _, startPositionInLine = parseBuffer.at()
    if startPositionInLine + len(substring) > len(parseBuffer):
        return False
    for i in range(len(substring)):
        if parseBuffer[startPositionInLine + i] != substring[i]:
            return False
    return True


def eatPythonString(parseBuffer):
    if parseBuffer.getCurrentChar() not in "\"'":
        generateParseError(parseBuffer, "python string", parseBuffer.getCurrentChar())
    quoteChar = parseBuffer.getCurrentChar()
    isDocstring = bufferHasSubstring(parseBuffer, quoteChar * 3)
    parseBuffer.skip(3 if isDocstring else 1)
    escaping = False
    consecutiveUnescapedQuotes = 0
    while True:
        if parseBuffer.getCurrentChar() == quoteChar and not escaping:
            if not isDocstring or consecutiveUnescapedQuotes == 2:
                break
            consecutiveUnescapedQuotes += 1
        else:
            consecutiveUnescapedQuotes = 0
        escaping = not escaping if parseBuffer.getCurrentChar() == "\\" else False
        parseBuffer.skip(1)
    parseBuffer.skip(1)


def decodeCStyleEscapes(string):
    return string.encode("latin1", "backslashreplace").decode("unicode-escape")


def parseArgumentFormat(parseBuffer, otherExpected=None):
    formatString = parseOneOfExpectedStrings(
        parseBuffer, [n for n in FORMATS.keys()], otherExpected=otherExpected
    )
    return FORMATS[formatString]


def parseFStringArgumentFormat(parseBuffer):
    if parseBuffer.getCurrentChar() != "f":
        generateParseError(
            parseBuffer,
            "f-string argument format",
            parseBuffer.getCurrentChar(),
        )
    parseBuffer.skip(1)
    fString = parseQuotedString(parseBuffer)
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
            macroArgumentFormat = ARGUMENT_FORMAT_SHORTHANDS_TO_ARGUMENT_FORMAT[char]
            if i - 1 > currentStringStart:
                addToStringBuilder(i - 1)
                addStringBuilderToArgumentFormat()
            argumentFormat.append(macroArgumentFormat)
            currentStringStart = i + 1
        escaping = not escaping if char == "%" else False
    addToStringBuilder()
    addStringBuilderToArgumentFormat()
    return argumentFormat


def parseMultilineScript(parseBuffer):
    if not parseBuffer.getCurrentChar() == "{":
        generateParseError(parseBuffer, "multi-line script", None)
    parseBuffer.skip(1)
    parseBuffer.eatWhitespace()
    if not parseBuffer.atEndOfLine():
        generateParseError(
            parseBuffer,
            None,
            "illegal non-whitespace character after multi-line script open. Script must start on next line after indent",
        )
    parseBuffer.newline()
    if parseBuffer.getCurrentChar() == "}":
        parseBuffer.skip(1)
        return ""
    indent = parseBuffer.readWhitespace()
    if not indent:
        generateParseError(parseBuffer, "indent or }", parseBuffer.getCurrentChar())
    lines = [parseBuffer.readRestOfLine()]
    parseBuffer.newline()
    while not parseBuffer.getCurrentChar() == "}":
        if not bufferHasSubstring(parseBuffer, indent):
            if not parseBuffer.getCurrentChar().isspace():
                generateParseError(parseBuffer, "indent or }", parseBuffer.getCurrentChar())
            generateParseError(parseBuffer, None, "inconsistent indentation")
        parseBuffer.skip(len(indent))
        lines.append(parseBuffer.readRestOfLine())
        parseBuffer.newline()
    parseBuffer.skip(1)
    return "\n".join(lines)


def parseScripts(parseBuffer):
    if parseBuffer.getCurrentChar() == "{":
        return parseMultilineScript(parseBuffer)
    return parseBuffer.readRestOfLine()
