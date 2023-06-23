from enum import Enum
import math
from ASPN import midiNoteToASPN


class MacroArgumentFormat(Enum):
    MIDI = 0
    ASPN = 1
    ASPN_UNICODE = 2
    PIANO = 3
    VELOCITY = 4

    def toMacroArgument(self, note, velocity):
        match (self):
            case MacroArgumentFormat.MIDI:
                return str(note)
            case MacroArgumentFormat.ASPN:
                return midiNoteToASPN(note, False)
            case MacroArgumentFormat.ASPN_UNICODE:
                return midiNoteToASPN(note)
            case MacroArgumentFormat.PIANO:
                return str(note - 20)
            case MacroArgumentFormat.VELOCITY:
                return str(velocity)


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


class MacroArgumentDefinition:
    def __init__(self, argumentFormat, replaceString=None, argumentNumberRange=UNBOUNDED_MANR):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString
        self.argumentNumberRange = argumentNumberRange

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString

    def numArgumentsAllowed(self, numArguments):
        return self.argumentNumberRange.test(numArguments)

    def __str__(self):
        argumentNumRangeString = f'[{self.argumentNumberRange.getLowerBound()}:{self.argumentNumberRange.getUpperBound()}]'
        replaceDefinitionString = f'"{self.replaceString}"→' if self.replaceString != None else ''
        argumentFormatString = self.argumentFormat.name if isinstance(self.argumentFormat, MacroArgumentFormat) else '|'.join(
            (s if isinstance(s, str) else str(s) for s in self.argumentFormat))
        return (f'*{argumentNumRangeString}({replaceDefinitionString}{argumentFormatString})')
