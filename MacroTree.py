import subprocess
from MacroTreeNode import MacroTreeNode
from ASPN import midiNoteToASPN
from MacroArgument import MacroArgumentFormat
from MacroArgument import MacroArgumentDefinition


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addSequenceToTree(self, sequence, script):
        if (len(sequence) == 0):
            return
        currentNode = self.root
        argumentDefinition = False
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

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, pressed):
        keysLeftToProcess = len(pressed) - position
        if (keysLeftToProcess == 0):
            for script, argumentDefinition in currentNode.getScripts():
                if (argumentDefinition != None):
                    replaceString = argumentDefinition.getReplaceString()
                    if (replaceString != None):
                        script = script.replace(replaceString, '')
                subprocess.Popen(script, shell=True)
            return
        for script, argumentDefinition in currentNode.getScripts():
            if (argumentDefinition == None):
                continue
            argumentFormat = argumentDefinition.getArgumentFormat()
            replaceString = argumentDefinition.getReplaceString()
            arguments = [(str(note) if argumentFormat == MacroArgumentFormat.MIDI else midiNoteToASPN(
                note)) for note in pressed[position:]]
            argumentString = ' '.join(arguments)
            if (replaceString != None):
                command = script.replace(replaceString, argumentString)
            else:
                command = f'{script} {argumentString}'
            subprocess.Popen(command, shell=True)
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
