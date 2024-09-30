from script.argument import MIDIMessageArgumentDefinition
from macro.macro_error import MacroError


class Macro:
    def __init__(self, triggers, script):
        self.triggers = triggers
        self.script = script
        if (
            self.triggers == None
            and type(self.script.argumentDefinition) != MIDIMessageArgumentDefinition
        ):
            # Wildcard trigger macro used with non-MIDIMessageArgumentDefinition
            raise MacroError(
                f"Wildcard trigger macros can only be used with a MIDI-message argument definition."
            )

    def getTriggers(self):
        return self.triggers

    def getScript(self):
        return self.script

    def __str__(self):
        return f'{"+".join(str(t) for t in self.triggers) if self.triggers else "*"} {self.script}'
