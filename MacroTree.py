import subprocess
from MacroTreeNode import MacroTreeNode
from MacroArgument import MacroArgumentDefinition, MacroArgumentFormat


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addSequenceToTree(self, sequence, script):
        if (len(sequence) == 0):
            return
        currentNode = self.root
        argumentDefinition = None
        i = 0
        for i, trigger in enumerate(sequence):
            if (not currentNode.hasBranch(trigger)):
                break
            currentNode = currentNode.getBranch(trigger)
        else:
            currentNode.addScript(script)
            return
        for trigger in sequence[i:]:
            if (isinstance(trigger, MacroArgumentDefinition)):
                argumentDefinition = trigger
                break
            currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(script, argumentDefinition)

    def executeMacros(self, pressed):
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, pressed)

    def executeNoArgScripts(self, currentNode):
        for script, argumentDefinition in currentNode.getScripts():
            if (argumentDefinition):
                if (not argumentDefinition.numArgumentsAllowed(0)):
                    continue
                if (argumentDefinition.getReplaceString()):
                    script = script.replace(
                        argumentDefinition.getReplaceString(), '')
            subprocess.Popen(script, shell=True)

    def executeScripts(self, currentNode, pressed, position):
        for script, argumentDefinition in currentNode.getScripts():
            numArgumentsLeft = len(pressed) - position
            if (not argumentDefinition or not argumentDefinition.numArgumentsAllowed(numArgumentsLeft)):
                continue
            argumentFormat = argumentDefinition.getArgumentFormat()
            replaceString = argumentDefinition.getReplaceString()
            if (isinstance(argumentFormat, MacroArgumentFormat)):
                argumentGenerator = (argumentFormat.toMacroArgument(
                    n, v) for n, v in pressed[position:])
            else:
                argumentGenerator = (''.join(af if isinstance(af, str) else af.toMacroArgument(
                    n, v) for af in argumentFormat) for n, v in pressed[position:])
            argumentString = ' '.join(argumentGenerator)
            if (replaceString):
                command = script.replace(replaceString, argumentString)
            elif (not argumentString.isspace()):
                command = f'{script} {argumentString}'
            else:
                command = script
            subprocess.Popen(command, shell=True)

    def testNoteWithTrigger(self, playedNote, trigger):
        note, velocity = playedNote
        expectedNote, velocityPredicate = trigger
        if (note != expectedNote): return False
        v = velocity
        VELOCITY = velocity
        return eval(velocityPredicate)

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, pressed):
        keysLeftToProcess = len(pressed) - position
        if (keysLeftToProcess == 0):
            self.executeNoArgScripts(currentNode)
            return
        self.executeScripts(currentNode, pressed, position)
        for trigger, nextNode in currentNode.getBranches().items():
            match (trigger[0]):
                case (tuple()):
                    chordLength = len(trigger)
                    if (chordLength <= keysLeftToProcess):
                        playedChord = pressed[position:position + chordLength]
                        playedChord.sort(key=lambda nv: nv[0])
                        for i in range(len(playedChord)):
                            if (not self.testNoteWithTrigger(playedChord[i], trigger[i])):
                                break
                        else:
                            self.recurseMacroTreeAndExecuteMacros(
                                nextNode, position + chordLength, pressed)
                case (int()):
                    if (self.testNoteWithTrigger(pressed[position], trigger)):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, pressed)
