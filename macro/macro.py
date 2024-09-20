class Macro:
    def __init__(self, triggers, script):
        self.triggers = triggers
        self.script = script

    def getTriggers(self):
        return self.triggers

    def getScript(self):
        return self.script

    def __str__(self):
        return f'{"+".join(str(t) for t in self.triggers) if self.triggers else "*"} {self.script}'
