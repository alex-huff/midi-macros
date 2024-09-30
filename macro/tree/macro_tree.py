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
        self.triggerlessScripts = []

    def getRoot(self):
        return self.root

    def addMacroToTree(self, macro):
        if macro.getTriggers() == None:
            self.triggerlessScripts.append(macro.getScript())
            return
        currentNode = self.root
        notesTillScriptExecution = list(
            accumulate(numNotesInTrigger(t) for t in reversed(macro.getTriggers()))
        )
        notesTillScriptExecution.reverse()
        for trigger, notes in zip(macro.getTriggers(), notesTillScriptExecution):
            currentNode.updateActionsTillScriptExecution(
                macro.getScript().getArgumentDefinition(), offset=notes
            )
            if currentNode.hasBranch(trigger):
                currentNode = currentNode.getBranch(trigger)
            else:
                currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(macro.getScript())

    def executeMacros(self, playedNotes, midiMessage=None):
        if self.triggerlessScripts and midiMessage:
            for script in self.triggerlessScripts:
                script.queueIfArgumentsMatch((midiMessage,))
        if not self.root.shouldProcessNumActions(
            len(playedNotes) + (1 if midiMessage else 0)
        ):
            return
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, playedNotes, midiMessage)

    def executeScripts(self, currentNode, playedNotes, position, midiMessage=None):
        keysLeftToProcess = len(playedNotes) - position
        if not currentNode.getScripts() or (midiMessage and keysLeftToProcess > 0):
            return
        arguments = (midiMessage,) if midiMessage else playedNotes[position:]
        for script in currentNode.getScripts():
            script.queueIfArgumentsMatch(arguments)

    def recurseMacroTreeAndExecuteMacros(
        self, currentNode, position, playedNotes, midiMessage=None
    ):
        addedActions = 1 if midiMessage else 0
        self.executeScripts(currentNode, playedNotes, position, midiMessage)
        keysLeftToProcess = len(playedNotes) - position
        if not keysLeftToProcess:
            return
        for trigger, nextNode in currentNode.getBranches().items():
            match (trigger):
                case MacroChord():
                    chordLength = len(trigger.getChord())
                    if len(
                        trigger.getChord()
                    ) > keysLeftToProcess or not nextNode.shouldProcessNumActions(
                        (keysLeftToProcess - chordLength) + addedActions
                    ):
                        continue
                    if testChordWithMacroChord(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + chordLength, playedNotes, midiMessage
                        )
                case MacroNote():
                    if not nextNode.shouldProcessNumActions(
                        keysLeftToProcess - 1 + addedActions
                    ):
                        continue
                    if testNoteWithMacroNote(playedNotes, position, trigger):
                        self.recurseMacroTreeAndExecuteMacros(
                            nextNode, position + 1, playedNotes, midiMessage
                        )

    def shutdown(self):
        self.recurseMacroTreeAndShutdownScripts(self.root)

    def recurseMacroTreeAndShutdownScripts(self, currentNode):
        for script in currentNode.getScripts():
            script.shutdown()
        for nextNode in currentNode.getBranches().values():
            self.recurseMacroTreeAndShutdownScripts(nextNode)
