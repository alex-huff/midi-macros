import subprocess
from itertools import islice, accumulate
from macro.tree.macro_tree_node import MacroTreeNode
from macro.macro_argument import MacroArgumentFormat
from macro.macro_note import MacroNote
from macro.macro_chord import MacroChord
from macro.matching import (
    testNoteWithMacroNote,
    testChordWithMacroChord,
    numNotesInTrigger,
)
from log.mm_logging import logError, exceptionStr


class MacroTree:
    def __init__(self):
        self.root = MacroTreeNode()

    def getRoot(self):
        return self.root

    def addMacroToTree(self, macro, script):
        currentNode = self.root
        notesTillScriptExecution = list(
            accumulate(numNotesInTrigger(t) for t in reversed(macro.getTriggers()))
        )
        notesTillScriptExecution.reverse()
        for trigger, notes in zip(macro.getTriggers(), notesTillScriptExecution):
            currentNode.updateNotesTillScriptExecution(
                macro.getArgumentDefinition(), offset=notes
            )
            if currentNode.hasBranch(trigger):
                currentNode = currentNode.getBranch(trigger)
            else:
                currentNode = currentNode.setBranch(trigger, MacroTreeNode())
        currentNode.addScript(script, macro.getArgumentDefinition())

    def executeMacros(self, playedNotes):
        if not self.root.shouldProcessNumNotes(len(playedNotes)):
            return
        self.recurseMacroTreeAndExecuteMacros(self.root, 0, playedNotes)

    def executeScript(self, script, interpreter):
        try:
            process = subprocess.Popen(
                interpreter if interpreter else script,
                stdin=subprocess.PIPE if interpreter else None,
                text=True,
                shell=True,
                start_new_session=True,
            )
            if interpreter:
                process.stdin.write(script)
                process.stdin.close()
        except Exception as exception:
            logError(f"failed to run script, {exceptionStr(exception)}")

    def executeNoArgScripts(self, currentNode):
        for script, argumentDefinition in currentNode.getScripts():
            scriptText = script.getScript()
            if argumentDefinition:
                if not argumentDefinition.numArgumentsAllowed(0):
                    continue
                if argumentDefinition.getReplaceString():
                    scriptText = scriptText.replace(
                        argumentDefinition.getReplaceString(), ""
                    )
            self.executeScript(scriptText, script.getInterpreter())

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
                scriptText = script.getScript().replace(replaceString, argumentString)
            elif not argumentString.isspace():
                scriptText = f"{script.getScript()} {argumentString}"
            else:
                scriptText = script
            self.executeScript(scriptText, script.getInterpreter())

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
