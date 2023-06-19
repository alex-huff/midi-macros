class MacroTreeNode:
    def __init__(self):
        self.branches = dict()
        self.scripts = []
        self.passExtraKeysAsArguments = False

    def setBranch(self, trigger, nextNode):
        self.branches[trigger] = nextNode
        return nextNode

    def hasBranch(self, trigger):
        return trigger in self.branches

    def getBranch(self, trigger):
        return self.branches[trigger]

    def getBranches(self):
        return self.branches

    def addScripts(self, scripts):
        self.scripts.extend(scripts)

    def getScripts(self):
        return self.scripts

    def setShouldPassExtraKeysAsArguments(self):
        self.passExtraKeysAsArguments = True

    def shouldPassExtraKeysAsArguments(self):
        return self.passExtraKeysAsArguments
