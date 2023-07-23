from itertools import accumulate
from macro.tree.macro_tree_node import MacroTreeNode
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.matching import (
    testNoteWithMacroNote,
    testChordWithMacroChord,
    numNotesInTrigger,
)


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addMacroToTree(self, macro):
        currentNode = self.root
        notesTillScriptExecution = list(
            accumulate(numNotesInTrigger(t) for t in reversed(macro.getTriggers()))
        )
        notesTillScriptExecution.reverse()
        for trigger, notes in zip(macro.getTriggers(), notesTillScriptExecution):
            currentNode.updateNotesTillScriptExecution(
                macro.getScript().getArgumentDefinition(), offset=notes
            )
            if currentNode.hasBranch(trigger):
                currentNode = currentNode.getBranch(trigger)
            else:
                currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(macro.getScript())

    def executeMacros(self, playedNotes):
        if not self.root.shouldProcessNumNotes(len(playedNotes)):
            return
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, playedNotes)

    def executeScripts(self, currentNode, playedNotes, position):
        if not currentNode.getScripts():
            return
        args = playedNotes[position:]
        for script in currentNode.getScripts():
            script.queueIfNumArgumentsAllowed(args)

    def recurseMacroTreeAndExecuteMacros(self, currentNode, position, playedNotes):
        self.executeScripts(currentNode, playedNotes, position)
        keysLeftToProcess = len(playedNotes) - position
        if not keysLeftToProcess:
            return
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
                    if testChordWithMacroChord(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + chordLength, playedNotes
                        )
                case (MacroNote()):
                    if not nextNode.shouldProcessNumNotes(keysLeftToProcess - 1):
                        continue
                    if testNoteWithMacroNote(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, playedNotes
                        )
    def shutdown(self):
        self.recurseMacroTreeAndShutdownScripts(self.root)

    def recurseMacroTreeAndShutdownScripts(self, currentNode):
        for script in currentNode.getScripts():
            script.shutdown()
        for nextNode in currentNode.getBranches().values():
            self.recurseMacroTreeAndShutdownScripts(nextNode)
