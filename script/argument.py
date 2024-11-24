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


class ArgumentFormat(ABC):
    @abstractmethod
    def convert(self, argument, data=None):
        pass

    @abstractmethod
    def __str__(self):
        pass


class NamedArgumentFormat(ArgumentFormat):
    def __init__(self, convertor, name):
        self.convertor = convertor
        self.name = name

    def getName(self):
        return self.name

    def convert(self, argument, data=None):
        return self.convertor(argument)

    def __str__(self):
        return self.getName()


class FStringArgumentFormat(ArgumentFormat):
    def __init__(self, fString):
        self.fString = fString

    def convert(self, argument, data=None):
        return self.evaluateFString(argument, data)

    @abstractmethod
    def evaluateFString(self, argument):
        pass

    def __str__(self):
        return self.fString


class NotesFStringArgumentFormat(FStringArgumentFormat):
    def __init__(self, fString):
        super().__init__(fString)

    def evaluateFString(self, pn, data=None):
        TRIGGER = data
        PLAYED_NOTE = pn
        MIDI = PLAYED_NOTE_FORMAT_MIDI.convert(pn)
        ASPN = PLAYED_NOTE_FORMAT_ASPN.convert(pn)
        ASPN_UNICODE = PLAYED_NOTE_FORMAT_ASPN_UNICODE.convert(pn)
        PIANO = PLAYED_NOTE_FORMAT_PIANO.convert(pn)
        VELOCITY = PLAYED_NOTE_FORMAT_VELOCITY.convert(pn)
        TIME = PLAYED_NOTE_FORMAT_TIME.convert(pn)
        CHANNEL = PLAYED_NOTE_FORMAT_CHANNEL.convert(pn)
        NONE = FORMAT_NONE.convert(pn)
        m = MIDI
        a = ASPN
        A = ASPN_UNICODE
        p = PIANO
        v = VELOCITY
        t = TIME
        c = CHANNEL
        n = NONE
        formattedString = eval(self.fString)
        if not isinstance(formattedString, str):
            raise ValueError
        return formattedString


class MIDIFStringArgumentFormat(FStringArgumentFormat):
    def __init__(self, fString):
        super().__init__(fString)

    def evaluateFString(self, message, data=None):
        TRIGGER = data
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
        formattedString = eval(self.fString)
        if not isinstance(formattedString, str):
            raise ValueError
        return formattedString


PLAYED_NOTE_FORMAT_MIDI = NamedArgumentFormat(lambda pn: pn.getNote(), "MIDI")
PLAYED_NOTE_FORMAT_ASPN = NamedArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote(), False), "ASPN"
)
PLAYED_NOTE_FORMAT_ASPN_UNICODE = NamedArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote()), "ASPN_UNICODE"
)
PLAYED_NOTE_FORMAT_PIANO = NamedArgumentFormat(lambda pn: pn.getNote() - 20, "PIANO")
PLAYED_NOTE_FORMAT_VELOCITY = NamedArgumentFormat(lambda pn: pn.getVelocity(), "VELOCITY")
PLAYED_NOTE_FORMAT_TIME = NamedArgumentFormat(lambda pn: pn.getTime(), "TIME")
PLAYED_NOTE_FORMAT_CHANNEL = NamedArgumentFormat(lambda pn: pn.getChannel(), "CHANNEL")

MIDI_MESSAGE_FORMAT_MESSAGE_BYTES = NamedArgumentFormat(
    lambda m: "-".join(str(d) for d in m.getMessage()), "MESSAGE_BYTES"
)
MIDI_MESSAGE_FORMAT_MESSAGE_BYTES_HEX = NamedArgumentFormat(
    lambda m: "-".join(hex(d) for d in m.getMessage()), "MESSAGE_BYTES_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_0 = NamedArgumentFormat(lambda m: m.getData0(), "DATA_0")
MIDI_MESSAGE_FORMAT_DATA_1 = NamedArgumentFormat(lambda m: m.getData1(), "DATA_1")
MIDI_MESSAGE_FORMAT_DATA_2 = NamedArgumentFormat(lambda m: m.getData2(), "DATA_2")
MIDI_MESSAGE_FORMAT_STATUS = NamedArgumentFormat(lambda m: m.getStatus(), "STATUS")
MIDI_MESSAGE_FORMAT_CHANNEL = NamedArgumentFormat(lambda m: m.getChannel(), "CHANNEL")
MIDI_MESSAGE_FORMAT_TIME = NamedArgumentFormat(lambda m: m.getTime(), "TIME")
MIDI_MESSAGE_FORMAT_STATUS_HEX = NamedArgumentFormat(
    lambda m: hex(m.getStatus()), "STATUS_HEX"
)
MIDI_MESSAGE_FORMAT_CHANNEL_HEX = NamedArgumentFormat(
    lambda m: hex(m.getChannel()), "CHANNEL_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_0_HEX = NamedArgumentFormat(
    lambda m: hex(m.getData0()), "DATA_0_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_1_HEX = NamedArgumentFormat(
    lambda m: hex(m.getData1()), "DATA_1_HEX"
)
MIDI_MESSAGE_FORMAT_DATA_2_HEX = NamedArgumentFormat(
    lambda m: hex(m.getData2()), "DATA_2_HEX"
)
MIDI_MESSAGE_FORMAT_CC_VALUE = MIDI_MESSAGE_FORMAT_DATA_2
MIDI_MESSAGE_FORMAT_CC_VALUE_PERCENT = NamedArgumentFormat(
    lambda m: round(100 * m.getData2() / 127) if m.getData2() != None else None,
    "CC_VALUE_PERCENT",
)
MIDI_MESSAGE_FORMAT_CC_VALUE_BOOL = NamedArgumentFormat(
    lambda m: m.getData2() >= 64 if m.getData2() != None else None,
    "CC_VALUE_BOOL",
)

FORMAT_NONE = NamedArgumentFormat(lambda a: "", "NONE")


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


class ArgumentProcessor(ABC):
    @abstractmethod
    def process(self, trigger, arguments):
        pass

    @abstractmethod
    def __str__(self):
        pass


class JoiningArgumentProcessor(ArgumentProcessor):
    def __init__(self, argumentSeparator, argumentFormat):
        super().__init__()
        self.argumentSeparator = argumentSeparator
        self.argumentFormat = argumentFormat

    def process(self, trigger, arguments):
        return (self.argumentSeparator or "").join(
            str(self.argumentFormat.convert(argument, trigger)) for argument in arguments
        )

    def __str__(self):
        argumentSeparatorSpecifier = (
            f'[{repr(self.argumentSeparator)}]' if self.argumentSeparator not in (None, " ") else ""
        )
        return f"{argumentSeparatorSpecifier}{self.argumentFormat}"


class ScriptPreprocessor(ArgumentProcessor):
    def __init__(self, replacements):
        super().__init__()
        self.replacements = replacements

    def process(self, trigger, arguments):
        return [
            (replaceString, argumentProcessor.process(trigger, arguments))
            for replaceString, argumentProcessor in self.replacements
        ]

    def __str__(self):
        return ",".join(
            f'{repr(replaceString)}→{argumentProcessor}' for replaceString, argumentProcessor in self.replacements
        )


PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER = "NOTES"
MIDI_ARGUMENT_DEFINITION_SPECIFIER = "MIDI"


class ArgumentDefinition(ABC):
    def __init__(
        self,
        argumentType=object,
        argumentProcessor=None,
        argumentNumberRange=UNBOUNDED_ARGUMENT_NUMBER_RANGE,
        matchPredicates=[]
    ):
        self.argumentType = argumentType
        self.argumentProcessor = argumentProcessor
        self.argumentNumberRange = argumentNumberRange
        self.matchPredicates = matchPredicates

    def getArgumentType(self):
        return self.argumentType

    def getArgumentProcessor(self):
        return self.argumentProcessor

    def getArgumentNumberRange(self):
        return self.argumentNumberRange

    def getMatchPredicates(self):
        return self.matchPredicates

    def shouldProcessArguments(self):
        return self.argumentProcessor != None

    def testNumArguments(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def argumentsMatch(self, trigger, arguments):
        return (
            self.testNumArguments(len(arguments))
            and self.verifyArgumentTypes(arguments)
            and self.testMatchPredicates(trigger, arguments)
        )

    def verifyArgumentTypes(self, arguments):
        return all(isinstance(argument, self.argumentType) for argument in arguments)

    def testMatchPredicates(self, trigger, arguments):
        matchPredicate = None
        try:
            for matchPredicate in self.matchPredicates:
                if not self.testMatchPredicate(matchPredicate, trigger, arguments):
                    return False
            return True
        except Exception:
            logError(f"failed to evaluate match predicate: {matchPredicate}")
            return False

    def processArguments(self, trigger, arguments):
        if not self.shouldProcessArguments():
            raise UnsupportedOperation
        return self.argumentProcessor.process(trigger, arguments)

    @abstractmethod
    def testMatchPredicate(self, matchPredicate, trigger, arguments):
        pass

    @abstractmethod
    def getIdentifier(self):
        pass

    def __str__(self):
        argumentNumRangeSpecifier = f"[{self.argumentNumberRange.getLowerBound()}:{self.argumentNumberRange.getUpperBound()}]"
        matchPredicatesSpecifier = "".join(
            f"{{{matchPredicate}}}" for matchPredicate in self.matchPredicates
        )
        argumentProcessorSpecifier = f"({self.argumentProcessor})" if self.shouldProcessArguments() else ""
        return f"{self.getIdentifier()}{argumentNumRangeSpecifier}{matchPredicatesSpecifier}{argumentProcessorSpecifier}"


class ZeroArgumentDefinition(ArgumentDefinition):
    def __init__(self):
        super().__init__(argumentNumberRange=ZERO_ARGUMENT_NUMBER_RANGE)

    def getIdentifier(self):
        return "0"

    def testMatchPredicate(self, matchPredicate, trigger, arguments):
        raise UnsupportedOperation


class PlayedNotesArgumentDefinition(ArgumentDefinition):
    def __init__(
        self,
        argumentNumberRange,
        matchPredicates,
        argumentProcessor=None
    ):
        super().__init__(
            PlayedNote,
            argumentProcessor,
            argumentNumberRange,
            matchPredicates
        )

    def getIdentifier(self):
        return PLAYED_NOTES_ARGUMENT_DEFINITION_SPECIFIER

    def testMatchPredicate(self, matchPredicate, trigger, arguments):
        TRIGGER = trigger
        NOTES = arguments
        CHANNEL = {n.getChannel() for n in NOTES}
        CHANNEL = tuple(CHANNEL)[0] if len(CHANNEL) == 1 else CHANNEL
        NOTES_START_TIME = NOTES_FINISH_TIME = NOTES_ELAPSED_TIME = (
            NOTES_MIN_VELOCITY
        ) = NOTES_MAX_VELOCITY = NOTES_AVERAGE_VELOCITY = None
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


class MIDIMessageArgumentDefinition(ArgumentDefinition):
    def __init__(
        self,
        matchPredicates,
        argumentProcessor=None
    ):
        super().__init__(
            MIDIMessage,
            argumentProcessor,
            argumentNumberRange=SINGLE_ARGUMENT_NUMBER_RANGE,
            matchPredicates=matchPredicates,
        )

    def getIdentifier(self):
        return "MIDI"

    def testMatchPredicate(self, matchPredicate, trigger, arguments):
        TRIGGER = trigger
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


ZERO_ARGUMENT_DEFINITION = ZeroArgumentDefinition()
