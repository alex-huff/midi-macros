import re
import math
from log.mm_logging import loggingContext, logInfo
from aspn import aspn
from parser.parse_buffer import ParseBuffer
from parser.parse_error import ParseError
from script.argument import *
from macro.tree.macro_tree import MacroTree
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.macro import Macro
from script.script import *


BASE_PITCH_REGEX = re.compile(r"[A-Ga-g]")
ARROW_START_CHARS = "→-"
MODIFIERS = "#♯b♭𝄪𝄫"
INDENT = "\t"
ARGUMENT_FORMATS = {
    "MIDI": FORMAT_MIDI,
    "ASPN": FORMAT_ASPN,
    "ASPN_UNICODE": FORMAT_ASPN_UNICODE,
    "PIANO": FORMAT_PIANO,
    "VELOCITY": FORMAT_VELOCITY,
    "TIME": FORMAT_TIME,
    "CHANNEL": FORMAT_CHANNEL,
    "NONE": FORMAT_NONE,
}


def generateParseError(parseBuffer, expected, got):
    expectedString = f"expected: {expected}\n" if expected else ""
    gotString = f"got: {got}\n" if got else ""
    raise ParseError(
        f"{expectedString}{gotString}while parsing:\n{parseBuffer}\n{parseBuffer.generateArrowLine()}",
        parseBuffer,
    )


def generateInvalidMIDIError(parseBuffer, note):
    raise ParseError(
        f"invalid MIDI note: {note}\n{parseBuffer}\n{parseBuffer.generateArrowLine()}",
        parseBuffer,
    )


def parseMacroFile(macroFile, source, profile, subprofile=None):
    with loggingContext(profile, subprofile):
        macroTree = MacroTree()
        lines = [line[:-1] for line in macroFile.readlines()]
        if not lines:
            return macroTree
        parseBuffer = ParseBuffer(lines, source)
        while not parseBuffer.atEndOfBuffer():
            macro = parseMacro(parseBuffer, profile, subprofile)
            logInfo(f"adding macro: {macro}")
            macroTree.addMacroToTree(macro)
            parseBuffer.skipTillData()
        return macroTree


def parseMacro(parseBuffer, profile, subprofile=None):
    triggers = parseTriggers(
        parseBuffer) if parseBuffer.getCurrentChar() != "*" else []
    parseBuffer.skipTillData()
    argumentDefinition = ZERO_ARGUMENT_DEFINITION
    parsedArgumentDefinition = False
    if parseBuffer.getCurrentChar() == "*":
        argumentDefinition = parsePlayedNoteArgumentDefinition(parseBuffer)
        parseBuffer.skipTillData()
        parsedArgumentDefinition = True
    interpreter = None
    parsedInterpreter = False
    if parseBuffer.getCurrentChar() == "(":
        interpreter = parseInterpreter(parseBuffer)
        parsedInterpreter = True
    scriptFlags = NONE
    parsedScriptFlags = False
    if parseBuffer.getCurrentChar() == "[":
        scriptFlags = parseScriptFlags(parseBuffer)
        parsedScriptFlags = True
    if parseBuffer.getCurrentChar() not in ARROW_START_CHARS:
        parsedAnything = any(
            (parsedArgumentDefinition, parsedInterpreter, parsedScriptFlags)
        )
        plusExpectedSpecifier = " or +" if not parsedAnything else ""
        argumentDefinitionExpectedSpecifier = (
            " or argument definition" if not parsedAnything else ""
        )
        interpreterExpectedSpecifier = (
            " or interpreter" if (
                not parsedInterpreter and not parsedScriptFlags) else ""
        )
        scriptFlagsExpectedSpecifier = " or script flags" if not parsedScriptFlags else ""
        generateParseError(
            parseBuffer,
            f"arrow operator (->, →){plusExpectedSpecifier}{argumentDefinitionExpectedSpecifier}{interpreterExpectedSpecifier}{scriptFlagsExpectedSpecifier}",
            parseBuffer.getCurrentChar(),
        )
    eatArrow(parseBuffer)
    parseBuffer.skipTillData()
    script = Script(parseScript(parseBuffer),
                    argumentDefinition, scriptFlags, interpreter, profile, subprofile)
    return Macro(triggers, script)


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
        if parseBuffer.getCurrentChar() == "(":
            parseBuffer.skip(1)
            parenthesizedTriggers = parseTriggers(parseBuffer)
            parseBuffer.skipTillData()
            if not parseBuffer.getCurrentChar() == ")":
                generateParseError(parseBuffer, ")",
                                   parseBuffer.getCurrentChar())
            parseBuffer.skip(1)
            matchPredicates = parseMatchPredicates(parseBuffer)
            for trigger in parenthesizedTriggers:
                trigger.addMatchPredicates(matchPredicates)
            triggers.extend(parenthesizedTriggers)
        else:
            triggers.append(parseTrigger(parseBuffer))
        afterTrigger = parseBuffer.at()
        parseBuffer.skipTillData()
        if parseBuffer.atEndOfBuffer() or parseBuffer.getCurrentChar() != "+":
            parseBuffer.jump(afterTrigger)
            return triggers
        parseBuffer.skip(1)


def parseTrigger(parseBuffer):
    if parseBuffer.getCurrentChar() == "[":
        return parseChord(parseBuffer)
    if parseBuffer.getCurrentChar().isdigit() or BASE_PITCH_REGEX.match(
        parseBuffer.getCurrentChar()
    ):
        return parseNote(parseBuffer)
    generateParseError(parseBuffer, "note or chord",
                       parseBuffer.getCurrentChar())


def parseChord(parseBuffer):
    if parseBuffer.getCurrentChar() != "[":
        generateParseError(parseBuffer, "chord", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    chord = []
    while True:
        parseBuffer.skipTillData()
        note = parseNote(parseBuffer)
        chord.append(note)
        parseBuffer.skipTillData()
        if parseBuffer.getCurrentChar() not in "|]":
            generateParseError(parseBuffer, "| or ]",
                               parseBuffer.getCurrentChar())
        if parseBuffer.getCurrentChar() == "]":
            parseBuffer.skip(1)
            chord.sort(key=lambda macroNote: macroNote.getNote())
            macroChord = MacroChord(tuple(chord))
            macroChord.addMatchPredicates(parseMatchPredicates(parseBuffer))
            return macroChord
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
    macroNote = MacroNote(note)
    macroNote.addMatchPredicates(parseMatchPredicates(parseBuffer))
    return macroNote


def parseASPNNote(parseBuffer):
    if not BASE_PITCH_REGEX.match(parseBuffer.getCurrentChar()):
        generateParseError(parseBuffer, "ASPN note",
                           parseBuffer.getCurrentChar())
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


def parseMatchPredicates(parseBuffer):
    matchPredicates = []
    while not parseBuffer.atEndOfLine() and parseBuffer.getCurrentChar() == "{":
        matchPredicates.append(parseMatchPredicate(parseBuffer))
    return matchPredicates


def parseMatchPredicate(parseBuffer):
    if parseBuffer.getCurrentChar() != "{":
        generateParseError(parseBuffer, "match predicate",
                           parseBuffer.getCurrentChar())
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


def parsePlayedNoteArgumentDefinition(parseBuffer):
    if parseBuffer.getCurrentChar() != "*":
        generateParseError(parseBuffer, "*", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    argumentNumberRange = UNBOUNDED_ARGUMENT_NUMBER_RANGE
    parsedArgumentNumberRange = False
    if parseBuffer.getCurrentChar() == "[":
        argumentNumberRange = parseArgumentNumberRange(parseBuffer)
        parsedArgumentNumberRange = True
    matchPredicates = []
    parsedMatchPredicates = False
    if parseBuffer.getCurrentChar() == "{":
        matchPredicates = parseMatchPredicates(parseBuffer)
        parsedMatchPredicates = True
    if parseBuffer.getCurrentChar() != "(":
        argumentNumberRangeExpectedSpecifier = " or argument number range" if (
            not parsedArgumentNumberRange and not parsedMatchPredicates) else ""
        matchPredicatesExpectedSpecifier = " or match predicates" if not parsedMatchPredicates else ""
        generateParseError(
            parseBuffer, f"argument definition body{argumentNumberRangeExpectedSpecifier}{matchPredicatesExpectedSpecifier}", parseBuffer.getCurrentChar())
    argumentFormat, replaceString, argumentSeperator = parseArgumentDefinitionBody(
        parseBuffer)
    return PlayedNoteArgumentDefinition(
        argumentFormat, replaceString, argumentSeperator, argumentNumberRange, matchPredicates)


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
            return ArgumentNumberRange(lowerBound, lowerBound)
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
        generateParseError(parseBuffer, "number or ]",
                           parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return ArgumentNumberRange(lowerBound, upperBound)


def parsePositiveInteger(parseBuffer):
    if not parseBuffer.getCurrentChar().isdigit():
        generateParseError(parseBuffer, "positive number",
                           parseBuffer.getCurrentChar())
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
    parsedReplaceString = False
    if parseBuffer.getCurrentChar() == '"':
        replaceString = parseQuotedString(parseBuffer)
        replaceString = replaceString if replaceString else None
        parseBuffer.eatWhitespace()
        eatArrow(parseBuffer)
        parseBuffer.eatWhitespace()
        parsedReplaceString = True
    argumentSeperator = " "
    parsedArgumentSeperator = False
    if parseBuffer.getCurrentChar() == "[":
        argumentSeperator = parseArgumentSeperator(parseBuffer)
        parsedArgumentSeperator = True
    if bufferHasSubstring(parseBuffer, 'f"'):
        argumentFormat = parseFStringArgumentFormat(parseBuffer)
    else:
        argumentFormatStringStart = parseBuffer.at()
        parseBuffer.skipTillChar(")")
        argumentFormatString = parseBuffer.stringFrom(
            argumentFormatStringStart, parseBuffer.at()
        )
        if not argumentFormatString in ARGUMENT_FORMATS:
            replaceStringExpectedSpecifier = (
                " or replace string"
                if (not parsedReplaceString and not parsedArgumentSeperator)
                else ""
            )
            argumentSeperatorExpectedSpecifier = (
                " or argument seperator" if not parsedArgumentSeperator else ""
            )
            otherExpectedSpecifier = f"f-string argument format{replaceStringExpectedSpecifier}{argumentSeperatorExpectedSpecifier}"
            parseBuffer.jump(argumentFormatStringStart)
            generateParseError(
                parseBuffer,
                f'one of {"|".join(ARGUMENT_FORMATS.keys())} or {otherExpectedSpecifier}',
                None,
            )
        argumentFormat = ARGUMENT_FORMATS[argumentFormatString]
    if parseBuffer.getCurrentChar() != ")":
        generateParseError(parseBuffer, ")", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return argumentFormat, replaceString, argumentSeperator


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


def readQuotedString(parseBuffer, quoteChar='"', returnString=True):
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
    if returnString:
        return parseBuffer.stringFrom(startPosition, endPosition)


def parseArgumentSeperator(parseBuffer):
    if parseBuffer.getCurrentChar() != "[":
        generateParseError(
            parseBuffer, "argument seperator", parseBuffer.getCurrentChar()
        )
    parseBuffer.skip(1)
    if parseBuffer.getCurrentChar() == '"':
        seperator = parseQuotedString(parseBuffer)
        if not parseBuffer.getCurrentChar() == "]":
            generateParseError(parseBuffer, "]", parseBuffer.getCurrentChar())
    else:
        startPosition = parseBuffer.at()
        parseBuffer.skipTillChar("]")
        seperator = parseBuffer.stringFrom(startPosition, parseBuffer.at())
    parseBuffer.skip(1)
    return seperator


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
        generateParseError(parseBuffer, "python string",
                           parseBuffer.getCurrentChar())
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


def parseFStringArgumentFormat(parseBuffer):
    if parseBuffer.getCurrentChar() != "f":
        generateParseError(
            parseBuffer,
            "f-string argument format",
            parseBuffer.getCurrentChar(),
        )
    fStringStart = parseBuffer.at()
    parseBuffer.skip(1)
    readQuotedString(parseBuffer, returnString=False)
    return parseBuffer.stringFrom(fStringStart, parseBuffer.at())


def parseInterpreter(parseBuffer):
    if not parseBuffer.getCurrentChar() == "(":
        generateParseError(parseBuffer, "interpreter",
                           parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    startPosition = parseBuffer.at()
    parseBuffer.eatWhitespace()
    if parseBuffer.getCurrentChar() == '"':
        interpreter = parseQuotedString(parseBuffer)
        parseBuffer.eatWhitespace()
        if not parseBuffer.getCurrentChar() == ")":
            generateParseError(parseBuffer, ")", parseBuffer.getCurrentChar())
    else:
        parseBuffer.skipTillChar(")")
        interpreter = parseBuffer.stringFrom(startPosition, parseBuffer.at())
    parseBuffer.skip(1)
    return interpreter


def parseScriptFlags(parseBuffer):
    if not parseBuffer.getCurrentChar() == "[":
        generateParseError(parseBuffer, "script flags",
                           parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    afterSeperator = parseBuffer.at()
    parseBuffer.eatWhitespace()
    flags = NONE
    while True:
        if parseBuffer.getCurrentChar() in "|]":
            parseBuffer.jump(afterSeperator)
            generateParseError(parseBuffer, None, "empty script flag")
        flagStart = parseBuffer.at()
        parseBuffer.skipTillChar("|]", terminateOnWhitespace=True)
        flag = parseBuffer.stringFrom(flagStart, parseBuffer.at())
        if flag not in FLAGS:
            parseBuffer.jump(flagStart)
            generateParseError(
                parseBuffer, f"one of {'|'.join(FLAGS.keys())}", flag)
        flags |= FLAGS[flag]
        parseBuffer.eatWhitespace()
        if parseBuffer.getCurrentChar() == "]":
            break
        elif parseBuffer.getCurrentChar() == "|":
            parseBuffer.skip(1)
            afterSeperator = parseBuffer.at()
            parseBuffer.eatWhitespace()
        else:
            generateParseError(parseBuffer, "| or ]",
                               parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return flags


def parseMultilineScript(parseBuffer):
    if not parseBuffer.getCurrentChar() == "{":
        generateParseError(
            parseBuffer,
            "multi-line script",
            parseBuffer.getCurrentChar() if not parseBuffer.atEndOfLine() else None,
        )
    parseBuffer.skip(1)
    parseBuffer.skipComment()
    if not parseBuffer.atEndOfLine():
        generateParseError(
            parseBuffer,
            None,
            "illegal non-whitespace character after multi-line script open. Script must start on next line after indent",
        )
    lines = []

    def skipEmptyLines():
        while parseBuffer.atEndOfLine():
            parseBuffer.newline()
            lines.append("")

    parseBuffer.newline()
    skipEmptyLines()
    while not parseBuffer.getCurrentChar() == "}":
        if not bufferHasSubstring(parseBuffer, INDENT):
            if not parseBuffer.getCurrentChar().isspace():
                generateParseError(
                    parseBuffer, "indent or }", parseBuffer.getCurrentChar()
                )
            generateParseError(parseBuffer, None, "incorrect indentation")
        parseBuffer.skip(len(INDENT))
        lines.append(parseBuffer.readRestOfLine())
        parseBuffer.newline()
        skipEmptyLines()
    parseBuffer.skip(1)
    return "\n".join(lines)


def parseScript(parseBuffer):
    if parseBuffer.getCurrentChar() == "{":
        return parseMultilineScript(parseBuffer)
    return parseBuffer.readRestOfLine()
