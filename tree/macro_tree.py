import subprocess
from itertools import islice, accumulate
from statistics import mean
from log.mm_logging import logError
from tree.macro_tree_node import MacroTreeNode
from macro.macro_argument import MacroArgumentFormat
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord


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

    def numNotesInTrigger(self, trigger):
        match (trigger):
            case (MacroNote()):
                return 1
            case (MacroChord()):
                return len(trigger.getChord())
            case (_):
                return 0

    def addMacroToTree(self, macro, script):
        currentNode = self.root
        notesToScriptExecution = list(
            accumulate(self.numNotesInTrigger(t) for t in reversed(macro.getTriggers()))
        )
        notesToScriptExecution.reverse()
        minArguments = (
            macro.getArgumentDefinition().getArgumentNumberRange().getLowerBound()
        )
        maxArguments = (
            macro.getArgumentDefinition().getArgumentNumberRange().getUpperBound()
        )

        def updateMinAndMaxForNode(node, notes):
            node.updateMinNotesTillScriptExecution(notes + minArguments)
            node.updateMaxNotesTillScriptExecution(notes + maxArguments)

        i = 0
        for i, (trigger, notes) in enumerate(
            zip(macro.getTriggers(), notesToScriptExecution)
        ):
            if not currentNode.hasBranch(trigger):
                break
            updateMinAndMaxForNode(currentNode, notes)
            currentNode = currentNode.getBranch(trigger)
        else:
            currentNode.addScript(script, macro.getArgumentDefinition())
            return
        for trigger, notes in islice(
            zip(macro.getTriggers(), notesToScriptExecution), i, None
        ):
            updateMinAndMaxForNode(currentNode, notes)
            currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(script, macro.getArgumentDefinition())

    def executeMacros(self, playedNotes):
        if not self.root.shouldProcessNumNotes(len(playedNotes)):
            return
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, playedNotes)

    def executeNoArgScripts(self, currentNode):
        for script, argumentDefinition in currentNode.getScripts():
            if argumentDefinition:
                if not argumentDefinition.numArgumentsAllowed(0):
                    continue
                if argumentDefinition.getReplaceString():
                    script = script.replace(argumentDefinition.getReplaceString(), "")
            subprocess.Popen(script, shell=True)

    def executeScripts(self, currentNode, playedNotes, position):
        for script, argumentDefinition in currentNode.getScripts():
            numArgumentsLeft = len(playedNotes) - position
            if not argumentDefinition or not argumentDefinition.numArgumentsAllowed(
                numArgumentsLeft
            ):
                continue
            argumentFormat = argumentDefinition.getArgumentFormat()
            replaceString = argumentDefinition.getReplaceString()
            if isinstance(argumentFormat, MacroArgumentFormat):
                argumentGenerator = (
                    argumentFormat.toMacroArgument(playedNote)
                    for playedNote in islice(playedNotes, position, None)
                )
            else:
                argumentGenerator = (
                    "".join(
                        af if isinstance(af, str) else af.toMacroArgument(playedNote)
                        for af in argumentFormat
                    )
                    for playedNote in islice(playedNotes, position, None)
                )
            argumentString = " ".join(argumentGenerator)
            if replaceString:
                command = script.replace(replaceString, argumentString)
            elif not argumentString.isspace():
                command = f"{script} {argumentString}"
            else:
                command = script
            subprocess.Popen(command, shell=True)

    def printMatchPredicateEvaluationError(self, matchPredicate):
        logError(f"failed to evaluate match predicate: {matchPredicate}")

    def testChordWithMacroChord(self, playedNotes, position, macroChord):
        chordLength = len(macroChord.getChord())
        chordStart, chordEnd = position, position + chordLength - 1
        playedChord = list(
            zip(
                range(chordStart, chordEnd + 1),
                islice(playedNotes, chordStart, chordEnd + 1),
            )
        )
        playedChord.sort(key=lambda ip: ip[1].getNote())
        for macroNote, (position, _) in zip(macroChord.getChord(), playedChord):
            if not self.testNoteWithMacroNote(playedNotes, position, macroNote):
                return False
        CHORD_START_TIME = playedNotes[chordStart].getTime()
        CHORD_FINISH_TIME = playedNotes[chordEnd].getTime()
        CHORD_ELAPSED_TIME = CHORD_FINISH_TIME - CHORD_START_TIME

        def velocityFromIP(ip):
            return ip[1].getVelocity()

        CHORD_MIN_VELOCITY = min(velocityFromIP(ip) for ip in playedChord)
        CHORD_MAX_VELOCITY = max(velocityFromIP(ip) for ip in playedChord)
        CHORD_AVERAGE_VELOCITY = mean(velocityFromIP(ip) for ip in playedChord)
        cst = CHORD_START_TIME
        cft = CHORD_FINISH_TIME
        cet = CHORD_ELAPSED_TIME
        cminv = CHORD_MIN_VELOCITY
        cmaxv = CHORD_MAX_VELOCITY
        cavgv = CHORD_AVERAGE_VELOCITY
        try:
            result = eval(macroChord.getMatchPredicate())
        except Exception:
            self.printMatchPredicateEvaluationError(macroChord.getMatchPredicate())
            return False
        return result

    def testNoteWithMacroNote(self, playedNotes, position, macroNote):
        playedNote = playedNotes[position]
        if playedNote.getNote() != macroNote.getNote():
            return False
        VELOCITY = playedNote.getVelocity()
        TIME = playedNote.getTime()
        ELAPSED_TIME = (
            None
            if position == 0
            else playedNote.getTime() - playedNotes[position - 1].getTime()
        )
        v = VELOCITY
        t = TIME
        et = ELAPSED_TIME
        try:
            result = eval(macroNote.getMatchPredicate())
        except Exception:
            self.printMatchPredicateEvaluationError(macroNote.getMatchPredicate())
            return False
        return result

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, playedNotes):
        keysLeftToProcess = len(playedNotes) - position
        if keysLeftToProcess == 0:
            self.executeNoArgScripts(currentNode)
            return
        self.executeScripts(currentNode, playedNotes, position)
        for trigger, nextNode in currentNode.getBranches().items():
            match (trigger):
                case (MacroChord()):
                    chordLength = len(trigger.getChord())
                    if len(
                        trigger.getChord()
                    ) > keysLeftToProcess or not nextNode.shouldProcessNumNotes(
                        keysLeftToProcess - chordLength
                    ):
                        continue
                    if self.testChordWithMacroChord(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + chordLength, playedNotes
                        )
                case (MacroNote()):
                    if not nextNode.shouldProcessNumNotes(keysLeftToProcess - 1):
                        continue
                    if self.testNoteWithMacroNote(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, playedNotes
                        )
