from enum import Enum
from ASPN import midiNoteToASPN


class MacroArgumentFormat(Enum):
    MIDI = 0
    ASPN = 1
    ASPN_UNICODE = 2
    PIANO = 3

    def toMacroArgument(self, note):
        match self:
            case MacroArgumentFormat.MIDI:
                return str(note)
            case MacroArgumentFormat.ASPN:
                return midiNoteToASPN(note, False)
            case MacroArgumentFormat.ASPN_UNICODE:
                return midiNoteToASPN(note)
            case MacroArgumentFormat.PIANO:
                return str(note - 20)


class MacroArgumentDefinition:
    def __init__(self, argumentFormat, replaceString=None):
        self.argumentFormat = argumentFormat
        self.replaceString = replaceString

    def getArgumentFormat(self):
        return self.argumentFormat

    def getReplaceString(self):
        return self.replaceString

    def __str__(self):
        replaceDefinitionString = f'{self.replaceString}→' if self.replaceString != None else ''
        return (f'Arguments({replaceDefinitionString}{self.argumentFormat.name})')
