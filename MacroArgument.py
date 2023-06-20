from enum import Enum


class MacroArgumentFormat(Enum):
    MIDI = 0
    ASPN = 1


class MacroArgumentDefinition:
    def __init__(self, argumentFormat, replaceString=None):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString
