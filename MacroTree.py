import subprocess
from itertools import islice
from MacroTreeNode import MacroTreeNode
from MacroArgument import MacroArgumentDefinition, MacroArgumentFormat
from MacroNote import MacroNote


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addMacroToTree(self, macro, script):
        if (len(macro) == 0):
            return
        currentNode = self.root
        argumentDefinition = None
        i = 0
        for i, trigger in enumerate(macro):
            if (not currentNode.hasBranch(trigger)):
                break
            currentNode = currentNode.getBranch(trigger)
        else:
            currentNode.addScript(script)
            return
        for trigger in macro[i:]:
            if (isinstance(trigger, MacroArgumentDefinition)):
                argumentDefinition = trigger
                break
            currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(script, argumentDefinition)

    def executeMacros(self, playedNotes):
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, playedNotes)

    def executeNoArgScripts(self, currentNode):
        for script, argumentDefinition in currentNode.getScripts():
            if (argumentDefinition):
                if (not argumentDefinition.numArgumentsAllowed(0)):
                    continue
                if (argumentDefinition.getReplaceString()):
                    script = script.replace(
                        argumentDefinition.getReplaceString(), '')
            subprocess.Popen(script, shell=True)

    def executeScripts(self, currentNode, playedNotes, position):
        for script, argumentDefinition in currentNode.getScripts():
            numArgumentsLeft = len(playedNotes) - position
            if (not argumentDefinition or not argumentDefinition.numArgumentsAllowed(numArgumentsLeft)):
                continue
            argumentFormat = argumentDefinition.getArgumentFormat()
            replaceString = argumentDefinition.getReplaceString()
            if (isinstance(argumentFormat, MacroArgumentFormat)):
                argumentGenerator = (argumentFormat.toMacroArgument(
                    playedNote) for playedNote in playedNotes[position:])
            else:
                argumentGenerator = (''.join(af if isinstance(af, str) else af.toMacroArgument(
                    playedNote) for af in argumentFormat) for playedNote in playedNotes[position:])
            argumentString = ' '.join(argumentGenerator)
            if (replaceString):
                command = script.replace(replaceString, argumentString)
            elif (not argumentString.isspace()):
                command = f'{script} {argumentString}'
            else:
                command = script
            subprocess.Popen(command, shell=True)

    def testNoteWithMacroNote(self, playedNote, macroNote, ELAPSED_TIME=None, CHORD_ELAPSED_TIME=None):
        if (playedNote.getNote() != macroNote.getNote()):
            return False
        VELOCITY = playedNote.getVelocity()
        TIME = playedNote.getTime()
        v = VELOCITY
        t = TIME
        et = ELAPSED_TIME
        cet = CHORD_ELAPSED_TIME
        print(v, t, et, cet)
        return eval(macroNote.getMatchPredicate())

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, playedNotes):
        def getElapsedTimeFromLastPlayedNote(position):
            return None if position == 0 else playedNotes[position].getTime() - playedNotes[position - 1].getTime()

        keysLeftToProcess = len(playedNotes) - position
        if (keysLeftToProcess == 0):
            self.executeNoArgScripts(currentNode)
            return
        self.executeScripts(currentNode, playedNotes, position)
        for trigger, nextNode in currentNode.getBranches().items():
            match (trigger):
                case (tuple()):
                    chordLength = len(trigger)
                    if (chordLength > keysLeftToProcess):
                        continue
                    chordStart, chordEnd = position, position + chordLength - 1
                    chordElapsedTime = playedNotes[chordEnd].getTime(
                    ) - playedNotes[chordStart].getTime()
                    playedChord = list(zip(
                        range(chordStart, chordEnd + 1), islice(playedNotes, chordStart, chordEnd + 1)))
                    playedChord.sort(key=lambda ip: ip[1].getNote())
                    for macroNote, (pos, playedNote) in zip(trigger, playedChord):
                        if (not self.testNoteWithMacroNote(playedNote, macroNote, ELAPSED_TIME=getElapsedTimeFromLastPlayedNote(pos), CHORD_ELAPSED_TIME=chordElapsedTime)):
                            break
                    else:
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + chordLength, playedNotes)
                case (MacroNote()):
                    if (self.testNoteWithMacroNote(playedNotes[position], trigger, ELAPSED_TIME=getElapsedTimeFromLastPlayedNote(position))):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, playedNotes)
