import math
from io import UnsupportedOperation
from abc import ABC, abstractmethod
from typing_extensions import override
from aspn.aspn import midiNoteToASPN
from log.mm_logging import logError


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


FORMAT_MIDI = ArgumentFormat(lambda pn: str(pn.getNote()), "MIDI")
FORMAT_ASPN = ArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote(), False), "ASPN"
)
FORMAT_ASPN_UNICODE = ArgumentFormat(
    lambda pn: midiNoteToASPN(pn.getNote()), "ASPN_UNICODE"
)
FORMAT_PIANO = ArgumentFormat(lambda pn: str(pn.getNote() - 20), "PIANO")
FORMAT_VELOCITY = ArgumentFormat(lambda pn: str(pn.getVelocity()), "VELOCITY")
FORMAT_TIME = ArgumentFormat(lambda pn: str(pn.getTime()), "TIME")
FORMAT_CHANNEL = ArgumentFormat(lambda pn: str(pn.getChannel()), "CHANNEL")
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


class ArgumentDefinition(ABC):
    def __init__(
        self,
        argumentFormat,
        replaceString=None,
        argumentSeperator=" ",
        argumentNumberRange=UNBOUNDED_ARGUMENT_NUMBER_RANGE,
        matchPredicates=[]
    ):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString
        self.argumentSeperator = argumentSeperator
        self.argumentNumberRange = argumentNumberRange
        self.matchPredicates = matchPredicates

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

    def testNumArguments(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def acceptsArgs(self):
        return self.argumentNumberRange.acceptsArgs()

    def argumentsMatch(self, arguments):
        return self.testNumArguments(len(arguments)) and self.testMatchPredicates(arguments)

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
        return self.argumentSeperator.join(self.processArgument(argument) for argument in arguments)

    @abstractmethod
    def processArgument(self, argument):
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
            f"{{{matchPredicate}}}" for matchPredicate in self.matchPredicates)
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
        return f"{self.getIdentifier()}{argumentNumRangeSpecifier}{matchPredicatesSpecifier}({replaceStringSpecifier}{argumentSeperatorSpecifier}{argumentFormatSpecifier})"


class ZeroArgumentDefinition(ArgumentDefinition):
    def __init__(self):
        super().__init__(FORMAT_NONE, argumentNumberRange=ZERO_ARGUMENT_NUMBER_RANGE)

    def getIdentifier(self):
        return "0"

    def testMatchPredicate(self, matchPredicate, arguments):
        raise UnsupportedOperation

    def processArgument(self, argument):
        raise UnsupportedOperation


class PlayedNoteArgumentDefinition(ArgumentDefinition):
    def __init__(self, argumentFormat, replaceString, argumentSeperator, argumentNumberRange, matchPredicates):
        super().__init__(argumentFormat, replaceString, argumentSeperator, argumentNumberRange, matchPredicates)
        if isinstance(self.argumentFormat, ArgumentFormat):
            self.argumentProcessor = self.argumentFormat.convert
        else:
            self.argumentProcessor = self.processFStringArgumentFormat

    def getIdentifier(self):
        return "*"

    def testMatchPredicate(self, matchPredicate, arguments):
        ARGUMENTS = arguments
        a = ARGUMENTS
        try:
            if eval(matchPredicate):
                return True
        except Exception:
            logError(f"failed to evaluate match predicate: {matchPredicate}")
        return False

    def processArgument(self, argument):
        return self.argumentProcessor(argument)

    def processFStringArgumentFormat(self, playedNote):
        MIDI = FORMAT_MIDI.convert(playedNote)
        ASPN = FORMAT_ASPN.convert(playedNote)
        ASPN_UNICODE = FORMAT_ASPN_UNICODE.convert(playedNote)
        PIANO = FORMAT_PIANO.convert(playedNote)
        VELOCITY = FORMAT_VELOCITY.convert(playedNote)
        TIME = FORMAT_TIME.convert(playedNote)
        CHANNEL = FORMAT_CHANNEL.convert(playedNote)
        NONE = FORMAT_NONE.convert(playedNote)
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


ZERO_ARGUMENT_DEFINITION = ZeroArgumentDefinition()
