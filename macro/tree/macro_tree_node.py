import math


class MacroTreeNode:
    def __init__(self):
        self.branches = dict()
        self.scripts = []
        self.minActionsTillScriptExecution = math.inf
        self.maxActionsTillScriptExecution = 0

    def setBranch(self, trigger, nextNode):
        self.branches[trigger] = nextNode
        return nextNode

    def hasBranch(self, trigger):
        return trigger in self.branches

    def getBranch(self, trigger):
        return self.branches[trigger]

    def getBranches(self):
        return self.branches

    def addScript(self, script):
        self.updateActionsTillScriptExecution(script.getArgumentDefinition())
        self.scripts.append(script)

    def getScripts(self):
        return self.scripts

    def updateMinActionsTillScriptExecution(self, notes):
        self.minActionsTillScriptExecution = min(self.minActionsTillScriptExecution, notes)

    def updateMaxActionsTillScriptExecution(self, notes):
        self.maxActionsTillScriptExecution = max(self.maxActionsTillScriptExecution, notes)

    def updateActionsTillScriptExecution(self, argumentDefinition, offset=0):
        self.updateMinActionsTillScriptExecution(
            argumentDefinition.getArgumentNumberRange().getLowerBound() + offset
        )
        self.updateMaxActionsTillScriptExecution(
            argumentDefinition.getArgumentNumberRange().getUpperBound() + offset
        )

    def shouldProcessNumActions(self, notes):
        return (
            self.minActionsTillScriptExecution
            <= notes
            <= self.maxActionsTillScriptExecution
        )
