from enum import Enum
import math
from aspn import midiNoteToASPN


class MacroArgumentFormat(Enum):
    MIDI = 0
    ASPN = 1
    ASPN_UNICODE = 2
    PIANO = 3
    VELOCITY = 4
    TIME = 5
    NONE = 6

    def toMacroArgument(self, playedNote):
        match (self):
            case (MacroArgumentFormat.MIDI):
                return str(playedNote.getNote())
            case (MacroArgumentFormat.ASPN):
                return midiNoteToASPN(playedNote.getNote(), False)
            case (MacroArgumentFormat.ASPN_UNICODE):
                return midiNoteToASPN(playedNote.getNote())
            case (MacroArgumentFormat.PIANO):
                return str(playedNote.getNote() - 20)
            case (MacroArgumentFormat.VELOCITY):
                return str(playedNote.getVelocity())
            case (MacroArgumentFormat.TIME):
                return str(playedNote.getTime())
            case (MacroArgumentFormat.NONE):
                return ''


class MacroArgumentNumberRange:
    def __init__(self, lowerBound, upperBound):
        self.lowerBound = lowerBound
        self.upperBound = upperBound

    def getLowerBound(self):
        return self.lowerBound

    def getUpperBound(self):
        return self.upperBound

    def test(self, numArguments):
        return self.lowerBound <= numArguments <= self.upperBound


UNBOUNDED_MANR = MacroArgumentNumberRange(0, math.inf)
ZERO_MANR = MacroArgumentNumberRange(0, 0)


class MacroArgumentDefinition:
    def __init__(self, argumentFormat, replaceString=None, argumentNumberRange=UNBOUNDED_MANR):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString
        self.argumentNumberRange = argumentNumberRange

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString

    def getArgumentNumberRange(self):
        return self.argumentNumberRange

    def numArgumentsAllowed(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def setArgumentNumberRange(self, argumentNumberRange):
        self.argumentNumberRange = argumentNumberRange

    def __str__(self):
        argumentNumRangeString = f'[{self.argumentNumberRange.getLowerBound()}:{self.argumentNumberRange.getUpperBound()}]'
        replaceDefinitionString = f'"{self.replaceString}"→' if self.replaceString else ''
        argumentFormatString = self.argumentFormat.name if isinstance(self.argumentFormat, MacroArgumentFormat) else '|'.join(
            (s if isinstance(s, str) else str(s) for s in self.argumentFormat))
        return (f'*{argumentNumRangeString}({replaceDefinitionString}{argumentFormatString})')


ZERO_ARGUMENT_DEFINITION = MacroArgumentDefinition(
    MacroArgumentFormat.NONE, argumentNumberRange=ZERO_MANR)
