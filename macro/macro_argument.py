import math
from aspn.aspn import midiNoteToASPN


class MacroArgumentFormat():
    def __init__(self, convertor, name):
        self.convertor = convertor
        self.name = name

    def toMacroArgument(self, playedNote):
        return self.convertor(playedNote)

    def getName(self):
        return self.name

    def __str__(self):
        return self.name


FORMAT_MIDI         = MacroArgumentFormat(lambda pn: str(pn.getNote()), 'MIDI')
FORMAT_ASPN         = MacroArgumentFormat(lambda pn: midiNoteToASPN(pn.getNote(), False), 'ASPN')
FORMAT_ASPN_UNICODE = MacroArgumentFormat(lambda pn: midiNoteToASPN(pn.getNote()), 'ASPN_UNICODE')
FORMAT_PIANO        = MacroArgumentFormat(lambda pn: str(pn.getNote() - 20), 'PIANO')
FORMAT_VELOCITY     = MacroArgumentFormat(lambda pn: str(pn.getVelocity()), 'VELOCITY')
FORMAT_TIME         = MacroArgumentFormat(lambda pn: str(pn.getTime()), 'TIME')
FORMAT_NONE         = MacroArgumentFormat(lambda _: '', 'NONE')
FORMATS = {
    'MIDI': FORMAT_MIDI,
    'ASPN': FORMAT_ASPN,
    'ASPN_UNICODE': FORMAT_ASPN_UNICODE,
    'PIANO': FORMAT_PIANO,
    'VELOCITY': FORMAT_VELOCITY,
    'TIME': FORMAT_TIME,
    'NONE': FORMAT_NONE
}


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
        argumentFormatString = self.argumentFormat.getName() if isinstance(self.argumentFormat, MacroArgumentFormat) else '|'.join(
            (s if isinstance(s, str) else str(s) for s in self.argumentFormat))
        return (f'*{argumentNumRangeString}({replaceDefinitionString}{argumentFormatString})')


ZERO_ARGUMENT_DEFINITION = MacroArgumentDefinition(
    FORMAT_NONE, argumentNumberRange=ZERO_MANR)
