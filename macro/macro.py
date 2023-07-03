class Macro:
    def __init__(self, triggers, argumentDefinition):
        self.triggers = triggers
        self.argumentDefinition = argumentDefinition

    def getTriggers(self):
        return self.triggers

    def getArgumentDefinition(self):
        return self.argumentDefinition

    def __str__(self):
        return (
            f'{"+".join(str(t) for t in self.triggers)}+{str(self.argumentDefinition)}'
        )
