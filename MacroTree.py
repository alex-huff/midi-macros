import subprocess
from itertools import islice
from MacroTreeNode import MacroTreeNode
from MacroArgument import MacroArgumentDefinition, MacroArgumentFormat
from MacroNote import MacroNote
from MacroChord import MacroChord


def nanoSecondsToSeconds(elapsedTime):
    return elapsedTime / 10**9


def nanoSecondsToMilliseconds(elapsedTime):
    return elapsedTime / 10**6


SECONDS = nanoSecondsToSeconds
sec = SECONDS
MILLISECONDS = nanoSecondsToMilliseconds
ms = MILLISECONDS


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
        for trigger in islice(macro, i, None):
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

    def testChordWithMacroChord(self, playedNotes, position, macroChord):
        chordLength = len(macroChord.getChord())
        chordStart, chordEnd = position, position + chordLength - 1
        CHORD_ELAPSED_TIME = playedNotes[chordEnd].getTime(
        ) - playedNotes[chordStart].getTime()
        playedChord = list(zip(
            range(chordStart, chordEnd + 1), islice(playedNotes, chordStart, chordEnd + 1)))
        playedChord.sort(key=lambda ip: ip[1].getNote())
        for macroNote, (position, _) in zip(macroChord.getChord(), playedChord):
            if (not self.testNoteWithMacroNote(playedNotes, position, macroNote)):
                return False
        cet = CHORD_ELAPSED_TIME
        return eval(macroChord.getMatchPredicate())

    def testNoteWithMacroNote(self, playedNotes, position, macroNote):
        playedNote = playedNotes[position]
        if (playedNote.getNote() != macroNote.getNote()):
            return False
        VELOCITY = playedNote.getVelocity()
        TIME = playedNote.getTime()
        ELAPSED_TIME = None if position == 0 else playedNote.getTime() - \
            playedNotes[position - 1].getTime()
        v = VELOCITY
        t = TIME
        et = ELAPSED_TIME
        return eval(macroNote.getMatchPredicate())

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, playedNotes):
        keysLeftToProcess = len(playedNotes) - position
        if (keysLeftToProcess == 0):
            self.executeNoArgScripts(currentNode)
            return
        self.executeScripts(currentNode, playedNotes, position)
        for trigger, nextNode in currentNode.getBranches().items():
            match (trigger):
                case (MacroChord()):
                    chordLength = len(trigger.getChord())
                    if (len(trigger.getChord()) > keysLeftToProcess):
                        continue
                    if (self.testChordWithMacroChord(playedNotes, position, trigger)):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + chordLength, playedNotes)
                case (MacroNote()):
                    if (self.testNoteWithMacroNote(playedNotes, position, trigger)):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, playedNotes)
