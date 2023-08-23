import math
from io import UnsupportedOperation
from statistics import mean
from abc import ABC, abstractmethod
from aspn.aspn import midiNoteToASPN
from log.mm_logging import logError
from listener.played_note import PlayedNote
from midi.midi_message import MIDIMessage
from midi.constants import *
from util.time_util import *
from util.math_util import *


class ArgumentFormat:
    def __init__(self, convertor, name):
        self.convertor = convertor
        self.name = name

    def convert(self, playedNote):
        return self.convertor(playedNote)

    def getName(self):
        return self.name

    def __str__(self):
        return self.getName()


PLAYED_NOTE_FORMAT_MIDI = ArgumentFormat(lambda pn: pn.getNote(), "MIDI")
PLAYED_NOTE_FORMAT_ASPN = ArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote(), False), "ASPN"
)
PLAYED_NOTE_FORMAT_ASPN_UNICODE = ArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote()), "ASPN_UNICODE"
)
PLAYED_NOTE_FORMAT_PIANO = ArgumentFormat(lambda pn: pn.getNote() - 20, "PIANO")
PLAYED_NOTE_FORMAT_VELOCITY = ArgumentFormat(lambda pn: pn.getVelocity(), "VELOCITY")
PLAYED_NOTE_FORMAT_TIME = ArgumentFormat(lambda pn: pn.getTime(), "TIME")
PLAYED_NOTE_FORMAT_CHANNEL = ArgumentFormat(lambda pn: pn.getChannel(), "CHANNEL")

MIDI_MESSAGE_FORMAT_MESSAGE_BYTES = ArgumentFormat(
    lambda m: "-".join(str(d) for d in m.getMessage()), "MESSAGE_BYTES"
)
MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX = ArgumentFormat(
    lambda m: "-".join(hex(d) for d in m.getMessage()), "MESSAGE_BYTES_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_0 = ArgumentFormat(lambda m: m.getData0(), "DATA_0")
MIDI_MESSAGE_FORMAT_DATA_1 = ArgumentFormat(lambda m: m.getData1(), "DATA_1")
MIDI_MESSAGE_FORMAT_DATA_2 = ArgumentFormat(lambda m: m.getData2(), "DATA_2")
MIDI_MESSAGE_FORMAT_STATUS = ArgumentFormat(lambda m: m.getStatus(), "STATUS")
MIDI_MESSAGE_FORMAT_CHANNEL = ArgumentFormat(lambda m: m.getChannel(), "CHANNEL")
MIDI_MESSAGE_FORMAT_TIME = ArgumentFormat(lambda m: m.getTime(), "TIME")
MIDI_MESSAGE_FORMAT_STATUS_HEX = ArgumentFormat(
    lambda m: hex(m.getStatus()), "STATUS_HEX"
)
MIDI_MESSAGE_FORMAT_CHANNEL_HEX = ArgumentFormat(
    lambda m: hex(m.getChannel()), "CHANNEL_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_0_HEX = ArgumentFormat(
    lambda m: hex(m.getData0()), "DATA_0_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_1_HEX = ArgumentFormat(
    lambda m: hex(m.getData1()), "DATA_1_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_2_HEX = ArgumentFormat(
    lambda m: hex(m.getData2()), "DATA_2_HEX"
)
MIDI_MESSAGE_FORMAT_CC_VALUE = MIDI_MESSAGE_FORMAT_DATA_2
MIDI_MESSAGE_FORMAT_CC_VALUE_PERCENT = ArgumentFormat(
    lambda m: round(100 * m.getData2() / 127) if m.getData2() != None else None,
    "CC_VALUE_PERCENT",
)
MIDI_MESSAGE_FORMAT_CC_VALUE_BOOL = ArgumentFormat(
    lambda m: m.getData2() >= 64 if m.getData2() != None else None,
    "CC_VALUE_BOOL",
)

FORMAT_NONE = ArgumentFormat(lambda _: "", "NONE")


class ArgumentNumberRange:
    def __init__(self, lowerBound, upperBound):
        self.lowerBound = lowerBound
        self.upperBound = upperBound

    def getLowerBound(self):
        return self.lowerBound

    def getUpperBound(self):
        return self.upperBound

    def test(self, numArguments):
        return self.lowerBound <= numArguments <= self.upperBound

    def acceptsArgs(self):
        return self.upperBound > 0


UNBOUNDED_ARGUMENT_NUMBER_RANGE = ArgumentNumberRange(0, math.inf)
ZERO_ARGUMENT_NUMBER_RANGE = ArgumentNumberRange(0, 0)
SINGLE_ARGUMENT_NUMBER_RANGE = ArgumentNumberRange(1, 1)


PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER = "NOTES"
MIDI_ARGUMENT_DEFINITION_SPECIFIER = "MIDI"


class ArgumentDefinition(ABC):
    def __init__(
        self,
        argumentType=object,
        argumentFormat=FORMAT_NONE,
        replaceString=None,
        argumentSeperator=" ",
        argumentNumberRange=UNBOUNDED_ARGUMENT_NUMBER_RANGE,
        matchPredicates=[],
        shouldProcessArguments=True,
    ):
        self.argumentType = argumentType
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString
        self.argumentSeperator = argumentSeperator
        self.argumentNumberRange = argumentNumberRange
        self.matchPredicates = matchPredicates
        self.shouldProcessArguments = shouldProcessArguments
        if isinstance(self.argumentFormat, ArgumentFormat):
            self.argumentProcessor = lambda a: str(self.argumentFormat.convert(a))
        else:
            self.argumentProcessor = self.processFStringArgumentFormat

    def getArgumentType(self):
        return self.argumentType

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString

    def getArgumentSeperator(self):
        return self.argumentSeperator

    def getArgumentNumberRange(self):
        return self.argumentNumberRange

    def getMatchPredicates(self):
        return self.matchPredicates

    def getShouldProcessArguments(self):
        return self.shouldProcessArguments

    def testNumArguments(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def argumentsMatch(self, arguments):
        return (
            self.testNumArguments(len(arguments))
            and self.verifyArgumentTypes(arguments)
            and self.testMatchPredicates(arguments)
        )

    def verifyArgumentTypes(self, arguments):
        return all(isinstance(argument, self.argumentType) for argument in arguments)

    def testMatchPredicates(self, arguments):
        matchPredicate = None
        try:
            for matchPredicate in self.matchPredicates:
                if not self.testMatchPredicate(matchPredicate, arguments):
                    return False
            return True
        except Exception:
            logError(f"failed to evaluate match predicate: {matchPredicate}")
            return False

    def processArguments(self, arguments):
        if not self.shouldProcessArguments:
            raise UnsupportedOperation
        return self.argumentSeperator.join(
            self.argumentProcessor(argument) for argument in arguments
        )

    @abstractmethod
    def processFStringArgumentFormat(self, argument):
        pass

    @abstractmethod
    def testMatchPredicate(self, matchPredicate, arguments):
        pass

    @abstractmethod
    def getIdentifier(self):
        pass

    def __str__(self):
        argumentNumRangeSpecifier = f"[{self.argumentNumberRange.getLowerBound()}:{self.argumentNumberRange.getUpperBound()}]"
        matchPredicatesSpecifier = "".join(
            f"{{{matchPredicate}}}" for matchPredicate in self.matchPredicates
        )
        if self.shouldProcessArguments:
            replaceStringSpecifier = (
                f'"{self.replaceString}"→' if self.replaceString else ""
            )
            argumentSeperatorSpecifier = (
                f'["{self.argumentSeperator}"]' if self.argumentSeperator != " " else ""
            )
            argumentFormatSpecifier = (
                self.argumentFormat.getName()
                if isinstance(self.argumentFormat, ArgumentFormat)
                else self.argumentFormat
            )
            argumentDefinitionBodySpecifier = f"({replaceStringSpecifier}{argumentSeperatorSpecifier}{argumentFormatSpecifier})"
        else:
            argumentDefinitionBodySpecifier = ""
        return f"{self.getIdentifier()}{argumentNumRangeSpecifier}{matchPredicatesSpecifier}{argumentDefinitionBodySpecifier}"


class ZeroArgumentDefinition(ArgumentDefinition):
    def __init__(self):
        super().__init__(
            argumentNumberRange=ZERO_ARGUMENT_NUMBER_RANGE, shouldProcessArguments=False
        )

    def getIdentifier(self):
        return "0"

    def testMatchPredicate(self, matchPredicate, arguments):
        raise UnsupportedOperation

    def processFStringArgumentFormat(self, argument):
        raise UnsupportedOperation


class PlayedNotesArgumentDefinition(ArgumentDefinition):
    def __init__(
        self,
        argumentNumberRange,
        matchPredicates,
        argumentFormat=FORMAT_NONE,
        replaceString=None,
        argumentSeperator=" ",
        shouldProcessArguments=True,
    ):
        super().__init__(
            PlayedNote,
            argumentFormat,
            replaceString,
            argumentSeperator,
            argumentNumberRange,
            matchPredicates,
            shouldProcessArguments,
        )

    def getIdentifier(self):
        return PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER

    def testMatchPredicate(self, matchPredicate, arguments):
        NOTES = arguments
        CHANNEL = {n.getChannel() for n in NOTES}
        CHANNEL = tuple(CHANNEL)[0] if len(CHANNEL) == 1 else CHANNEL
        NOTES_START_TIME = (
            NOTES_FINISH_TIME
        ) = (
            NOTES_ELAPSED_TIME
        ) = NOTES_MIN_VELOCITY = NOTES_MAX_VELOCITY = NOTES_AVERAGE_VELOCITY = None
        if len(arguments) > 0:
            NOTES_START_TIME = NOTES[0].getTime()
            NOTES_FINISH_TIME = NOTES[-1].getTime()
            NOTES_ELAPSED_TIME = NOTES_FINISH_TIME - NOTES_START_TIME
            NOTES_MIN_VELOCITY = min(n.getVelocity() for n in NOTES)
            NOTES_MAX_VELOCITY = max(n.getVelocity() for n in NOTES)
            NOTES_AVERAGE_VELOCITY = mean(n.getVelocity() for n in NOTES)
        CHANNELS = [n.getChannel() for n in NOTES]
        VELOCITIES = [n.getVelocity() for n in NOTES]
        TIMES = [n.getTime() for n in NOTES]
        ELAPSED_TIMES = [
            (TIMES[i] - TIMES[i - 1]) if i > 0 else 0 for i in range(len(TIMES))
        ]
        ns = NOTES
        c = CHANNEL
        nst = NOTES_START_TIME
        nft = NOTES_FINISH_TIME
        net = NOTES_ELAPSED_TIME
        nminv = NOTES_MIN_VELOCITY
        nmaxv = NOTES_MAX_VELOCITY
        navgv = NOTES_AVERAGE_VELOCITY
        cs = CHANNELS
        vs = VELOCITIES
        ts = TIMES
        ets = ELAPSED_TIMES
        if eval(matchPredicate):
            return True
        return False

    def processFStringArgumentFormat(self, playedNote):
        PLAYED_NOTE = playedNote
        MIDI = PLAYED_NOTE_FORMAT_MIDI.convert(playedNote)
        ASPN = PLAYED_NOTE_FORMAT_ASPN.convert(playedNote)
        ASPN_UNICODE = PLAYED_NOTE_FORMAT_ASPN_UNICODE.convert(playedNote)
        PIANO = PLAYED_NOTE_FORMAT_PIANO.convert(playedNote)
        VELOCITY = PLAYED_NOTE_FORMAT_VELOCITY.convert(playedNote)
        TIME = PLAYED_NOTE_FORMAT_TIME.convert(playedNote)
        CHANNEL = PLAYED_NOTE_FORMAT_CHANNEL.convert(playedNote)
        NONE = FORMAT_NONE.convert(playedNote)
        pn = PLAYED_NOTE
        m = MIDI
        a = ASPN
        A = ASPN_UNICODE
        p = PIANO
        v = VELOCITY
        t = TIME
        c = CHANNEL
        n = NONE
        formattedString = eval(self.argumentFormat)
        if not isinstance(formattedString, str):
            raise ValueError
        return formattedString


class MIDIMessageArgumentDefinition(ArgumentDefinition):
    def __init__(
        self,
        matchPredicates,
        argumentFormat=FORMAT_NONE,
        replaceString=None,
        shouldProcessArguments=True,
    ):
        super().__init__(
            MIDIMessage,
            argumentFormat,
            replaceString,
            argumentNumberRange=SINGLE_ARGUMENT_NUMBER_RANGE,
            matchPredicates=matchPredicates,
            shouldProcessArguments=shouldProcessArguments,
        )

    def getIdentifier(self):
        return "MIDI"

    def testMatchPredicate(self, matchPredicate, arguments):
        MESSAGE = arguments[0]
        DATA_0 = MESSAGE.getData0()
        DATA_1 = MESSAGE.getData1()
        DATA_2 = MESSAGE.getData2()
        STATUS = MESSAGE.getStatus()
        CHANNEL = MESSAGE.getChannel()
        TIME = MESSAGE.getTime()
        CC_VALUE = DATA_2
        CC_FUNCTION = DATA_1
        m = MESSAGE
        d0 = DATA_0
        d1 = DATA_1
        d2 = DATA_2
        s = STATUS
        c = CHANNEL
        t = TIME
        ccv = CC_VALUE
        ccf = CC_FUNCTION
        if eval(matchPredicate):
            return True
        return False

    def processFStringArgumentFormat(self, message):
        MESSAGE = message
        MESSAGE_BYTES = MIDI_MESSAGE_FORMAT_MESSAGE_BYTES.convert(message)
        MESSAGE_BYTES_HEX = MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX.convert(message)
        DATA_0 = MIDI_MESSAGE_FORMAT_DATA_0.convert(message)
        DATA_1 = MIDI_MESSAGE_FORMAT_DATA_1.convert(message)
        DATA_2 = MIDI_MESSAGE_FORMAT_DATA_2.convert(message)
        STATUS = MIDI_MESSAGE_FORMAT_STATUS.convert(message)
        CHANNEL = MIDI_MESSAGE_FORMAT_CHANNEL.convert(message)
        TIME = MIDI_MESSAGE_FORMAT_TIME.convert(message)
        STATUS_HEX = MIDI_MESSAGE_FORMAT_STATUS_HEX.convert(message)
        CHANNEL_HEX = MIDI_MESSAGE_FORMAT_CHANNEL_HEX.convert(message)
        DATA_0_HEX = MIDI_MESSAGE_FORMAT_DATA_0_HEX.convert(message)
        DATA_1_HEX = MIDI_MESSAGE_FORMAT_DATA_1_HEX.convert(message)
        DATA_2_HEX = MIDI_MESSAGE_FORMAT_DATA_2_HEX.convert(message)
        CC_VALUE = MIDI_MESSAGE_FORMAT_CC_VALUE.convert(message)
        CC_VALUE_PERCENT = MIDI_MESSAGE_FORMAT_CC_VALUE_PERCENT.convert(message)
        CC_VALUE_BOOL = MIDI_MESSAGE_FORMAT_CC_VALUE_BOOL.convert(message)
        NONE = FORMAT_NONE.convert(message)
        CC_FUNCTION = DATA_1
        DATA_1_SCALED = lambda minValue, maxValue: lerp(
            (DATA_1 / 127), minValue, maxValue
        )
        DATA_2_SCALED = lambda minValue, maxValue: lerp(
            (DATA_2 / 127), minValue, maxValue
        )
        CC_VALUE_SCALED = DATA_2_SCALED
        m = MESSAGE
        mbs = MESSAGE_BYTES
        mbsh = MESSAGE_BYTES_HEX
        d0 = DATA_0
        d1 = DATA_1
        d2 = DATA_2
        s = STATUS
        c = CHANNEL
        t = TIME
        sh = STATUS_HEX
        ch = CHANNEL_HEX
        d0h = DATA_0_HEX
        d1h = DATA_1_HEX
        d2h = DATA_2_HEX
        ccvp = CC_VALUE_PERCENT
        ccvb = CC_VALUE_BOOL
        ccv = CC_VALUE
        ccf = CC_FUNCTION
        n = NONE
        formattedString = eval(self.argumentFormat)
        if not isinstance(formattedString, str):
            raise ValueError
        return formattedString


ZERO_ARGUMENT_DEFINITION = ZeroArgumentDefinition()
