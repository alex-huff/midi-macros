import math
from aspn.aspn import midiNoteToASPN


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


UNBOUNDED_ARGUMENT_NUMBER_RANGE = ArgumentNumberRange(0, math.inf)
ZERO_ARGUMENT_NUMBER_RANGE = ArgumentNumberRange(0, 0)


class ArgumentDefinition:
    def __init__(
        self,
        argumentFormat,
        replaceString=None,
        argumentSeperator=" ",
        argumentNumberRange=UNBOUNDED_ARGUMENT_NUMBER_RANGE,
    ):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString
        self.argumentSeperator = argumentSeperator
        self.argumentNumberRange = argumentNumberRange

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString

    def getArgumentSeperator(self):
        return self.argumentSeperator

    def getArgumentNumberRange(self):
        return self.argumentNumberRange

    def testNumArguments(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def setArgumentNumberRange(self, argumentNumberRange):
        self.argumentNumberRange = argumentNumberRange

    def __str__(self):
        argumentNumRangeSpecifier = f"[{self.argumentNumberRange.getLowerBound()}:{self.argumentNumberRange.getUpperBound()}]"
        replaceStringSpecifier = (
            f'"{self.replaceString}"→' if self.replaceString else ""
        )
        argumentSeperatorSpecifier = (
            f'["{self.argumentSeperator}"]' if self.argumentSeperator != " " else ""
        )
        argumentFormatSpecifier = (
            self.argumentFormat.getName()
            if isinstance(self.argumentFormat, ArgumentFormat)
            else "|".join(
                s if isinstance(s, str) else str(s) for s in self.argumentFormat
            )
        )
        return f"*{argumentNumRangeSpecifier}({replaceStringSpecifier}{argumentSeperatorSpecifier}{argumentFormatSpecifier})"


ZERO_ARGUMENT_DEFINITION = ArgumentDefinition(
    FORMAT_NONE, argumentNumberRange=ZERO_ARGUMENT_NUMBER_RANGE
)
