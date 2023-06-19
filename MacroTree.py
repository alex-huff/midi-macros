import subprocess
from MacroTreeNode import MacroTreeNode


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addSequenceToTree(self, sequence, scripts):
        if (len(sequence) == 0):
            return
        currentNode = self.root
        i = 0
        for i, trigger in enumerate(sequence):
            if (not currentNode.hasBranch(trigger)):
                break
            currentNode = currentNode.getBranch(trigger)
        else:
            currentNode.addScripts(scripts)
            return
        for trigger in sequence[i:]:
            if (trigger == -1):
                currentNode.setShouldPassExtraKeysAsArguments()
                break
            currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScripts(scripts)

    def executeMacros(self, pressed):
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, pressed)

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, pressed):
        keysLeftToProcess = len(pressed) - position
        if (keysLeftToProcess == 0):
            for script in currentNode.getScripts():
                subprocess.Popen(script)
            return
        if (currentNode.shouldPassExtraKeysAsArguments()):
            arguments = [str(note) for note in pressed[position:]]
            for script in currentNode.getScripts():
                command = [script]
                command.extend(arguments)
                subprocess.Popen(command)
        for trigger, nextNode in currentNode.getBranches().items():
            match trigger:
                case tuple():
                    chordLength = len(trigger)
                    if (chordLength <= keysLeftToProcess):
                        playedChord = pressed[position:position + chordLength]
                        playedChord.sort()
                        if (tuple(playedChord) == trigger):
                            self.recurseMacroTreeAndExecuteMacros(
                                nextNode, position + chordLength, pressed)
                case int():
                    if (pressed[position] == trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, pressed)
