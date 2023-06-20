class MacroTreeNode:
    def __init__(self):
        self.branches = dict()
        self.scripts = []

    def setBranch(self, trigger, nextNode):
        self.branches[trigger] = nextNode
        return nextNode

    def hasBranch(self, trigger):
        return trigger in self.branches

    def getBranch(self, trigger):
        return self.branches[trigger]

    def getBranches(self):
        return self.branches

    def addScript(self, script, argumentDefinition=None):
        self.scripts.append((script, argumentDefinition))

    def getScripts(self):
        return self.scripts
