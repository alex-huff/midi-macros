import math


class MacroTreeNode:
    def __init__(self):
        self.branches = dict()
        self.scripts = []
        self.minNotesTillScriptExecution = math.inf
        self.maxNotesTillScriptExecution = 0

    def setBranch(self, trigger, nextNode):
        self.branches[trigger] = nextNode
        return nextNode

    def hasBranch(self, trigger):
        return trigger in self.branches

    def getBranch(self, trigger):
        return self.branches[trigger]

    def getBranches(self):
        return self.branches

    def addScript(self, script, argumentDefinition):
        self.updateNotesTillScriptExecution(argumentDefinition)
        self.scripts.append((script, argumentDefinition))

    def getScripts(self):
        return self.scripts

    def updateMinNotesTillScriptExecution(self, notes):
        self.minNotesTillScriptExecution = min(self.minNotesTillScriptExecution, notes)

    def updateMaxNotesTillScriptExecution(self, notes):
        self.maxNotesTillScriptExecution = max(self.maxNotesTillScriptExecution, notes)

    def updateNotesTillScriptExecution(self, argumentDefinition, offset=0):
        self.updateMinNotesTillScriptExecution(
            argumentDefinition.getArgumentNumberRange().getLowerBound() + offset
        )
        self.updateMaxNotesTillScriptExecution(
            argumentDefinition.getArgumentNumberRange().getUpperBound() + offset
        )

    def shouldProcessNumNotes(self, notes):
        return (
            self.minNotesTillScriptExecution
            <= notes
            <= self.maxNotesTillScriptExecution
        )
