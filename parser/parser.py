import re
import math
from log.mm_logging import loggingContext, logInfo
from aspn import aspn
from parser.parse_buffer import ParseBuffer
from parser.parse_error import ParseError
from script.argument import *
from macro.tree.macro_tree import MacroTree
from macro.macro_error import MacroError
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.macro import Macro
from script.script_error import ScriptError
from script.script import *


BASE_PITCH_REGEX = re.compile(r"[A-Ga-g]")
ARROW_START_CHARS = "→-"
MODIFIERS = "#♯b♭𝄪𝄫"
INDENT = "    "
PLAYED_NOTE_NAMED_ARGUMENT_FORMATS = {
    argumentFormat.getName(): argumentFormat for argumentFormat in (
        PLAYED_NOTE_FORMAT_MIDI,
        PLAYED_NOTE_FORMAT_ASPN,
        PLAYED_NOTE_FORMAT_ASPN_UNICODE,
        PLAYED_NOTE_FORMAT_PIANO,
        PLAYED_NOTE_FORMAT_VELOCITY,
        PLAYED_NOTE_FORMAT_TIME,
        PLAYED_NOTE_FORMAT_CHANNEL,
        FORMAT_NONE
    )
}
MIDI_NAMED_ARGUMENT_FORMATS = {
    argumentFormat.getName(): argumentFormat for argumentFormat in (
        MIDI_MESSAGE_FORMAT_MESSAGE_BYTES,
        MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX,
        MIDI_MESSAGE_FORMAT_DATA_0,
        MIDI_MESSAGE_FORMAT_DATA_1,
        MIDI_MESSAGE_FORMAT_DATA_2,
        MIDI_MESSAGE_FORMAT_STATUS,
        MIDI_MESSAGE_FORMAT_CHANNEL,
        MIDI_MESSAGE_FORMAT_TIME,
        MIDI_MESSAGE_FORMAT_STATUS_HEX,
        MIDI_MESSAGE_FORMAT_CHANNEL_HEX,
        MIDI_MESSAGE_FORMAT_DATA_0_HEX,
        MIDI_MESSAGE_FORMAT_DATA_1_HEX,
        MIDI_MESSAGE_FORMAT_DATA_2_HEX,
        MIDI_MESSAGE_FORMAT_CC_VALUE_PERCENT,
        MIDI_MESSAGE_FORMAT_CC_VALUE_BOOL,
        FORMAT_NONE
    )
}
MIDI_NAMED_ARGUMENT_FORMATS["CC_VALUE"] = MIDI_MESSAGE_FORMAT_CC_VALUE
PLAYED_NOTE_ARGUMENT_FORMATS = (PLAYED_NOTE_NAMED_ARGUMENT_FORMATS, NotesFStringArgumentFormat)
MIDI_ARGUMENT_FORMATS = (MIDI_NAMED_ARGUMENT_FORMATS, MIDIFStringArgumentFormat)


def generateParseError(parseBuffer, expected, got=None, help=None):
    expectedString = f"expected: {expected}\n" if expected else ""
    gotString = f"got: {got}\n" if got else ""
    helpString = f"{help}\n" if help else ""
    raise ParseError(
        f"{helpString}{expectedString}{gotString}while parsing:\n{parseBuffer}\n{parseBuffer.generateArrowLine()}",
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
        lines = [line.rstrip("\n") for line in macroFile.readlines()]
        if not lines:
            return macroTree
        parseBuffer = ParseBuffer(lines, source)
        while not parseBuffer.atEndOfBuffer():
            beforeMacro = parseBuffer.at()
            try:
                macro = parseMacro(parseBuffer, profile, subprofile)
            except (MacroError, ScriptError) as error:
                parseBuffer.jump(beforeMacro)
                error.message = (
                    f"Failed to create macro starting at:\n{parseBuffer}\n{parseBuffer.generateArrowLine()}\n"
                    + error.message
                )
                raise error
            logInfo(f"adding macro: {macro}")
            macroTree.addMacroToTree(macro)
            parseBuffer.skipTillData()
        return macroTree


def bufferAtArgumentDefinitionSpecifier(parseBuffer):
    return bufferHasSubstring(
        parseBuffer, PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER
    ) or bufferHasSubstring(parseBuffer, MIDI_ARGUMENT_DEFINITION_SPECIFIER)


def parseMacro(parseBuffer, profile, subprofile=None):
    atArgumentDefinitionSpecifier = bufferAtArgumentDefinitionSpecifier(parseBuffer)
    if not atArgumentDefinitionSpecifier and not (
        parseBuffer.getCurrentChar() == "["
        or parseBuffer.getCurrentChar() == "("
        or parseBuffer.getCurrentChar() == "*"
        or parseBuffer.getCurrentChar().isdigit()
        or BASE_PITCH_REGEX.match(parseBuffer.getCurrentChar())
    ):
        generateParseError(
            parseBuffer, "trigger or argument definition", parseBuffer.getCurrentChar()
        )
    triggers = []
    parsedTriggers = False
    if not atArgumentDefinitionSpecifier:
        triggers = parseTriggers(parseBuffer)
        parseBuffer.skipTillData()
        parsedTriggers = True
        atArgumentDefinitionSpecifier = bufferAtArgumentDefinitionSpecifier(parseBuffer)
    argumentDefinition = ZERO_ARGUMENT_DEFINITION
    parsedArgumentDefinition = False
    if atArgumentDefinitionSpecifier:
        argumentDefinition = parseArgumentDefinition(parseBuffer)
        parseBuffer.skipTillData()
        parsedArgumentDefinition = True
    interpreter = None
    parsedInterpreter = False
    if parseBuffer.getCurrentChar() == "(":
        interpreter = parseInterpreter(parseBuffer)
        parsedInterpreter = True
    flags = NONE
    keyValueFlags = {}
    parsedScriptFlags = False
    if parseBuffer.getCurrentChar() == "[":
        flags, keyValueFlags = parseScriptFlags(parseBuffer)
        parsedScriptFlags = True
    if parseBuffer.getCurrentChar() not in ARROW_START_CHARS:
        parsedAnything = any(
            (parsedArgumentDefinition, parsedInterpreter, parsedScriptFlags)
        )
        argumentDefinitionExpectedSpecifier = (
            " or argument definition" if not parsedAnything else ""
        )
        interpreterExpectedSpecifier = (
            " or interpreter"
            if (not parsedInterpreter and not parsedScriptFlags)
            else ""
        )
        scriptFlagsExpectedSpecifier = (
            " or script flags" if not parsedScriptFlags else ""
        )
        generateParseError(
            parseBuffer,
            f"arrow operator (->, →){argumentDefinitionExpectedSpecifier}{interpreterExpectedSpecifier}{scriptFlagsExpectedSpecifier}",
            parseBuffer.getCurrentChar(),
        )
    eatArrow(parseBuffer)
    parseBuffer.skipTillData()
    script = Script(
        parseScript(parseBuffer),
        argumentDefinition,
        flags,
        keyValueFlags,
        interpreter,
        profile,
        subprofile,
    )
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
    if parseBuffer.getCurrentChar() == "*": # wildcard trigger
        parseBuffer.skip(1)
        return None
    triggers = []
    while True:
        parseBuffer.skipTillData()
        if parseBuffer.getCurrentChar() == "(":
            parseBuffer.skip(1)
            parenthesizedTriggers = parseTriggers(parseBuffer)
            parseBuffer.skipTillData()
            if not parseBuffer.getCurrentChar() == ")":
                generateParseError(parseBuffer, ")", parseBuffer.getCurrentChar())
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
    generateParseError(parseBuffer, "trigger", parseBuffer.getCurrentChar())


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
            generateParseError(parseBuffer, "| or ]", parseBuffer.getCurrentChar())
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
            case "#" | "♯":
                offset += 1
            case "b" | "♭":
                offset -= 1
            case "𝄪":
                offset += 2
            case "𝄫":
                offset -= 2
            case _:
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
        generateParseError(parseBuffer, "match predicate", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    startPosition = parseBuffer.at()
    parseBuffer.skipTillData(skipComments=False)
    numUnmatchedOpenLeftCurlyBraces = 0
    while numUnmatchedOpenLeftCurlyBraces > 0 or parseBuffer.getCurrentChar() != "}":
        match (parseBuffer.getCurrentChar()):
            case "{":
                numUnmatchedOpenLeftCurlyBraces += 1
            case "}":
                numUnmatchedOpenLeftCurlyBraces -= 1
            case '"' | "'":
                eatPythonString(parseBuffer)
                parseBuffer.skipTillData(skipComments=False)
                continue
        if numUnmatchedOpenLeftCurlyBraces < 0:
            generateParseError(parseBuffer, None, "unmatched curly brace")
        parseBuffer.skip(1)
        parseBuffer.skipTillData(skipComments=False)
    endPosition = parseBuffer.at()
    if startPosition == endPosition:
        generateParseError(parseBuffer, None, "empty match predicate")
    matchPredicate = parseBuffer.stringFrom(startPosition, endPosition).strip()
    parseBuffer.skip(1)
    return matchPredicate


def parseArgumentDefinition(parseBuffer):
    if not (
        bufferHasSubstring(parseBuffer, PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER)
        or bufferHasSubstring(parseBuffer, MIDI_ARGUMENT_DEFINITION_SPECIFIER)
    ):
        generateParseError(
            parseBuffer,
            f"{PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER} or {MIDI_ARGUMENT_DEFINITION_SPECIFIER} (argument definition specifier)",
            parseBuffer.getCurrentChar(),
        )
    isPlayedNotesArgumentDefinition = False
    if bufferHasSubstring(parseBuffer, PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER):
        parseBuffer.skip(len(PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER))
        isPlayedNotesArgumentDefinition = True
    else:
        parseBuffer.skip(len(MIDI_ARGUMENT_DEFINITION_SPECIFIER))
    argumentNumberRange = UNBOUNDED_ARGUMENT_NUMBER_RANGE
    if isPlayedNotesArgumentDefinition and parseBuffer.getCurrentChar() == "[":
        argumentNumberRange = parseArgumentNumberRange(parseBuffer)
    matchPredicates = []
    if parseBuffer.getCurrentChar() == "{":
        matchPredicates = parseMatchPredicates(parseBuffer)
    argumentProcessor = None
    if parseBuffer.getCurrentChar() == "(":
        argumentProcessor = parseArgumentProcessor(
            parseBuffer,
            *(PLAYED_NOTE_ARGUMENT_FORMATS if isPlayedNotesArgumentDefinition else MIDI_ARGUMENT_FORMATS),
            allowArgumentSeparator=isPlayedNotesArgumentDefinition,
        )
    if isPlayedNotesArgumentDefinition:
        return PlayedNotesArgumentDefinition(argumentNumberRange, matchPredicates, argumentProcessor=argumentProcessor)
    return MIDIMessageArgumentDefinition(matchPredicates, argumentProcessor=argumentProcessor)


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
        generateParseError(parseBuffer, "number or ]", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return ArgumentNumberRange(lowerBound, upperBound)


def parsePositiveInteger(parseBuffer):
    if not parseBuffer.getCurrentChar().isdigit():
        generateParseError(parseBuffer, "positive number", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    while not parseBuffer.atEndOfLine() and parseBuffer.getCurrentChar().isdigit():
        parseBuffer.skip(1)
    return int(parseBuffer.stringFrom(startPosition, parseBuffer.at()))


def parseArgumentProcessor(parseBuffer, namedArgumentFormats, fStringArgumentFormatType, allowArgumentSeparator=True):
    def parseJoiningArgumentProcessor():
        argumentSeparator = " " if allowArgumentSeparator else None
        parsedArgumentSeparator = False
        if allowArgumentSeparator and parseBuffer.getCurrentChar() == "[":
            argumentSeparator = parseArgumentSeparator(parseBuffer)
            parsedArgumentSeparator = True
        atOpeningParen = parseBuffer.getCurrentChar() == "("
        if bufferHasSubstring(parseBuffer, 'f"') or bufferHasSubstring(parseBuffer, "f'") or atOpeningParen:
            if atOpeningParen:
                fString = readParenthesisedStrings(parseBuffer, fStringsAllowed=True)
            else:
                fString = readFString(parseBuffer)
            return JoiningArgumentProcessor(argumentSeparator, fStringArgumentFormatType(fString))
        else:
            namedArgumentFormatStringStart = parseBuffer.at()
            parseBuffer.skipTillChar(",)", terminateOnWhitespace=True, terminateAtEndOfLine=True)
            namedArgumentFormatString = parseBuffer.stringFrom(
                namedArgumentFormatStringStart, parseBuffer.at()
            )
            if not namedArgumentFormatString in namedArgumentFormats:
                replaceStringExpectedSpecifier = (
                    " or replace string"
                    if (not parsedReplaceString and not parsedArgumentSeparator)
                    else ""
                )
                argumentSeparatorExpectedSpecifier = (
                    " or argument separator"
                    if allowArgumentSeparator and not parsedArgumentSeparator
                    else ""
                )
                otherExpectedSpecifier = f"parenthesized? f-string argument format{replaceStringExpectedSpecifier}{argumentSeparatorExpectedSpecifier}"
                parseBuffer.jump(namedArgumentFormatStringStart)
                generateParseError(
                    parseBuffer,
                    f'one of {"|".join(namedArgumentFormats.keys())} or {otherExpectedSpecifier}',
                )
            return JoiningArgumentProcessor(argumentSeparator, namedArgumentFormats[namedArgumentFormatString])

    if parseBuffer.getCurrentChar() != "(":
        generateParseError(
            parseBuffer,
            "argument processor",
            parseBuffer.getCurrentChar(),
        )
    parseBuffer.skip(1)
    parseBuffer.skipTillData()
    parsedReplaceString = False
    if parseBuffer.getCurrentChar() in "\"'":
        parsedReplaceString = True
        replacements = []
        while parseBuffer.getCurrentChar() in "\"'":
            replaceString = parsePythonStrings(parseBuffer)
            parseBuffer.eatWhitespace()
            eatArrow(parseBuffer)
            parseBuffer.eatWhitespace()
            replacements.append((replaceString, parseJoiningArgumentProcessor()))
            parseBuffer.skipTillData()
            if parseBuffer.getCurrentChar() == ",":
                parseBuffer.skip(1)
                parseBuffer.skipTillData()
            elif parseBuffer.getCurrentChar() != ")":
                generateParseError(
                    parseBuffer,
                    ", or )",
                    parseBuffer.getCurrentChar(),
                )
        if parseBuffer.getCurrentChar() != ")":
            generateParseError(
                parseBuffer,
                "replace string or )",
                parseBuffer.getCurrentChar(),
            )
        argumentProcessor = ScriptPreprocessor(replacements)
    else:
        argumentProcessor = parseJoiningArgumentProcessor()
        parseBuffer.skipTillData()
        if parseBuffer.getCurrentChar() != ")":
            generateParseError(parseBuffer, ")", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    return argumentProcessor


def parseArgumentSeparator(parseBuffer):
    if parseBuffer.getCurrentChar() != "[":
        generateParseError(
            parseBuffer, "argument separator", parseBuffer.getCurrentChar()
        )
    parseBuffer.skip(1)
    if parseBuffer.getCurrentChar() in "\"'":
        separator = parsePythonStrings(parseBuffer)
        if not parseBuffer.getCurrentChar() == "]":
            generateParseError(parseBuffer, "]", parseBuffer.getCurrentChar())
    else:
        startPosition = parseBuffer.at()
        parseBuffer.skipTillChar("]")
        separator = parseBuffer.stringFrom(startPosition, parseBuffer.at())
    parseBuffer.skip(1)
    return separator


def bufferHasSubstring(parseBuffer, substring):
    _, startPositionInLine = parseBuffer.at()
    if startPositionInLine + len(substring) > len(parseBuffer):
        return False
    for i in range(len(substring)):
        if parseBuffer[startPositionInLine + i] != substring[i]:
            return False
    return True


def parseParenthesisedStrings(parseBuffer):
    parenthesisedString = readParenthesisedStrings(parseBuffer)
    try:
        evaluatedString = eval(parenthesisedString)
        assert isinstance(evaluatedString, str)
        return evaluatedString
    except Exception as exception:
        parseBuffer.jump(stringStart)
        raise ParseError(
            f"failed to evaluate parenthesised string: {parenthesisedString}, {exception}", parseBuffer
        )


def readParenthesisedStrings(parseBuffer, fStringsAllowed=False, returnString=True):
    def inspectPosition():
        nonlocal atClosingParen, startsWithQuote, startsWithFString
        atClosingParen = parseBuffer.getCurrentChar() == ")"
        startsWithQuote = parseBuffer.getCurrentChar() in "\"'"
        startsWithFString = bufferHasSubstring(parseBuffer, 'f"') or bufferHasSubstring(parseBuffer, "f'")

    atClosingParen = startsWithQuote = startsWithFString = False
    startPosition = parseBuffer.at()
    if not parseBuffer.getCurrentChar() == "(":
        generateParseError(parseBuffer, "parenthesised strings", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    parseBuffer.skip(1)
    parseBuffer.skipTillData(skipComments=False)
    inspectPosition()
    while not atClosingParen:
        if not startsWithQuote and not (fStringsAllowed and startsWithFString):
            fStringExpectedSpecifier = " or f-string" if fStringsAllowed else ""
            generateParseError(parseBuffer, f"python string{fStringExpectedSpecifier} or )", parseBuffer.getCurrentChar())
        eatPythonStrings(parseBuffer, fStringsAllowed=fStringsAllowed)
        parseBuffer.skipTillData(skipComments=False)
        inspectPosition()
    parseBuffer.skip(1)
    endPosition = parseBuffer.at()
    if returnString:
        return parseBuffer.stringFrom(startPosition, endPosition)


def eatParenthesisedStrings(parseBuffer, fStringsAllowed=False):
    readParenthisedStrings(parseBuffer, fStringsAllowed=fStringsAllowed, returnString=False)


def parsePythonStrings(parseBuffer):
    return parsePythonString(parseBuffer, combineConsecutive=True)


def readPythonStrings(parseBuffer, fStringsAllowed=False, returnString=True):
    def inspectPosition():
        nonlocal atEndOfLine, startsWithQuote, startsWithFString
        atEndOfLine = parseBuffer.atEndOfLine()
        startsWithQuote = parseBuffer.getCurrentChar() in "\"'" if not atEndOfLine else False
        startsWithFString = bufferHasSubstring(parseBuffer, 'f"') or bufferHasSubstring(parseBuffer, "f'")

    atEndOfLine = startsWithQuote = startsWithFString = False
    inspectPosition()
    if not startsWithQuote and not (fStringsAllowed and startsWithFString):
        fStringExpectedSpecifier = " or f-string" if fStringsAllowed else ""
        generateParseError(parseBuffer, f"python string{fStringExpectedSpecifier}", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    while not atEndOfLine:
        if fStringsAllowed and startsWithFString:
            parseBuffer.skip(1)
        elif not startsWithQuote:
            break
        eatPythonString(parseBuffer)
        inspectPosition()
    endPosition = parseBuffer.at()
    if returnString:
        return parseBuffer.stringFrom(startPosition, endPosition)


def eatPythonStrings(parseBuffer, fStringsAllowed=False):
    readPythonStrings(parseBuffer, fStringsAllowed=fStringsAllowed, returnString=False)


def parsePythonString(parseBuffer, combineConsecutive=False):
    stringStart = parseBuffer.at()
    if combineConsecutive:
        pythonString = readPythonStrings(parseBuffer)
    else:
        pythonString = readPythonString(parseBuffer)
    try:
        evaluatedString = eval(pythonString)
        assert isinstance(evaluatedString, str)
        return evaluatedString
    except Exception as exception:
        parseBuffer.jump(stringStart)
        raise ParseError(
            f"failed to evaluate python string: {pythonString}, {exception}", parseBuffer
        )


def readPythonString(parseBuffer, returnString=True):
    if parseBuffer.getCurrentChar() not in "\"'":
        generateParseError(parseBuffer, "python string", parseBuffer.getCurrentChar())
    startPosition = parseBuffer.at()
    quoteChar = parseBuffer.getCurrentChar()
    isDocstring = bufferHasSubstring(parseBuffer, quoteChar * 3)
    parseBuffer.skip(3 if isDocstring else 1)
    escaping = False
    consecutiveUnescapedQuotes = 0
    while True:
        atEndOfLine = parseBuffer.atEndOfLine()
        if isDocstring and atEndOfLine:
            consecutiveUnescapedQuotes = 0
            escaping = False
            parseBuffer.newline()
            continue
        if parseBuffer.getCurrentChar() == quoteChar and not escaping:
            if not isDocstring or consecutiveUnescapedQuotes == 2:
                break
            consecutiveUnescapedQuotes += 1
        else:
            consecutiveUnescapedQuotes = 0
        escaping = not escaping if parseBuffer.getCurrentChar() == "\\" else False
        parseBuffer.skip(1)
    parseBuffer.skip(1)
    endPosition = parseBuffer.at()
    if returnString:
        return parseBuffer.stringFrom(startPosition, endPosition)


def eatPythonString(parseBuffer):
    readPythonString(parseBuffer, returnString=False)


def readFString(parseBuffer):
    if not (bufferHasSubstring(parseBuffer, 'f"') or bufferHasSubstring(parseBuffer, "f'")):
        generateParseError(
            parseBuffer,
            "f-string",
            parseBuffer.getCurrentChar(),
        )
    return readPythonStrings(parseBuffer, fStringsAllowed=True)


def parseInterpreter(parseBuffer):
    if not parseBuffer.getCurrentChar() == "(":
        generateParseError(parseBuffer, "interpreter", parseBuffer.getCurrentChar())
    outerStart = parseBuffer.at()
    parseBuffer.skip(1)
    innerStart = parseBuffer.at()
    parseBuffer.skipTillData(skipComments=False)
    if parseBuffer.getCurrentChar() in "\"'":
        parseBuffer.jump(outerStart)
        return parseParenthesisedStrings(parseBuffer)
    else:
        parseBuffer.multilineSkipTillChar(")")
        interpreter = parseBuffer.stringFrom(innerStart, parseBuffer.at())
    parseBuffer.skip(1)
    return interpreter


def parseScriptFlags(parseBuffer):
    if not parseBuffer.getCurrentChar() == "[":
        generateParseError(parseBuffer, "script flags", parseBuffer.getCurrentChar())
    parseBuffer.skip(1)
    afterSeparator = parseBuffer.at()
    parseBuffer.eatWhitespace()
    flags = NONE
    keyValueFlags = {}
    while True:
        if parseBuffer.getCurrentChar() in "|]=":
            parseBuffer.jump(afterSeparator)
            generateParseError(parseBuffer, None, "empty script flag")
        flagStart = parseBuffer.at()
        parseBuffer.skipTillChar("|]=", terminateOnWhitespace=True)
        flag = parseBuffer.stringFrom(flagStart, parseBuffer.at())
        parseBuffer.eatWhitespace()
        parsedKeyValue = False
        isKeyValueFlag = parseBuffer.getCurrentChar() == "="
        flagDict = KEY_VALUE_FLAGS if isKeyValueFlag else FLAGS
        if flag not in flagDict:
            parseBuffer.jump(flagStart)
            generateParseError(parseBuffer, f"one of {'|'.join(flagDict.keys())}", flag)
        if isKeyValueFlag:
            parseBuffer.skip(1)
            parseBuffer.eatWhitespace()
            atOpeningParen = parseBuffer.getCurrentChar() == "("
            match (KEY_VALUE_FLAGS[flag]):
                case FlagType.STRING_TYPE:
                    if atOpeningParen:
                        value = parseParenthesisedStrings(parseBuffer)
                    elif parseBuffer.getCurrentChar() in "\"'":
                        value = parsePythonStrings(parseBuffer)
                    else:
                        valueStart = parseBuffer.at()
                        parseBuffer.skipTillChar("|]", terminateOnWhitespace=True)
                        value = parseBuffer.stringFrom(valueStart, parseBuffer.at())
                case FlagType.FSTRING_TYPE:
                    if not (bufferHasSubstring(parseBuffer, 'f"') or bufferHasSubstring(parseBuffer, "f'") or atOpeningParen):
                        generateParseError(
                            parseBuffer,
                            f"parenthesized? f-string value for {flag}",
                            parseBuffer.getCurrentChar(),
                        )
                    if atOpeningParen:
                        value = readParenthesisedStrings(parseBuffer, fStringsAllowed=True)
                    else:
                        value = readFString(parseBuffer)
            keyValueFlags[flag] = value
            parseBuffer.eatWhitespace()
            parsedKeyValue = True
        else:
            flags |= FLAGS[flag]
        if parseBuffer.getCurrentChar() == "]":
            break
        elif parseBuffer.getCurrentChar() == "|":
            parseBuffer.skip(1)
            afterSeparator = parseBuffer.at()
            parseBuffer.eatWhitespace()
        else:
            equalsExpectedSpecifier = " or =" if not parsedKeyValue else ""
            generateParseError(
                parseBuffer,
                f"| or ]{equalsExpectedSpecifier}",
                parseBuffer.getCurrentChar(),
            )
    parseBuffer.skip(1)
    return flags, keyValueFlags


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
