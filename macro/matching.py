from itertools import islice
from statistics import mean
from log.mm_logging import logError
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


def numNotesInTrigger(trigger):
    match (trigger):
        case (MacroNote()):
            return 1
        case (MacroChord()):
            return len(trigger.getChord())
        case (list()):
            return sum(numNotesInTrigger(t) for t in trigger)
        case (_):
            return 0


def testChordWithMacroChord(playedNotes, position, macroChord):
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
        if not testNoteWithMacroNote(playedNotes, position, macroNote):
            return False
    CHANNEL = {ip[1].getChannel() for ip in playedChord}
    CHANNEL = tuple(CHANNEL)[0] if len(CHANNEL) == 1 else CHANNEL
    CHORD_START_TIME = playedNotes[chordStart].getTime()
    CHORD_FINISH_TIME = playedNotes[chordEnd].getTime()
    CHORD_ELAPSED_TIME = CHORD_FINISH_TIME - CHORD_START_TIME

    def velocityFromIP(ip):
        return ip[1].getVelocity()

    CHORD_MIN_VELOCITY = min(velocityFromIP(ip) for ip in playedChord)
    CHORD_MAX_VELOCITY = max(velocityFromIP(ip) for ip in playedChord)
    CHORD_AVERAGE_VELOCITY = mean(velocityFromIP(ip) for ip in playedChord)
    c = CHANNEL
    cst = CHORD_START_TIME
    cft = CHORD_FINISH_TIME
    cet = CHORD_ELAPSED_TIME
    cminv = CHORD_MIN_VELOCITY
    cmaxv = CHORD_MAX_VELOCITY
    cavgv = CHORD_AVERAGE_VELOCITY
    try:
        result = eval(macroChord.getMatchPredicate())
    except Exception:
        logMatchPredicateEvaluationError(macroChord.getMatchPredicate())
        return False
    return result


def testNoteWithMacroNote(playedNotes, position, macroNote):
    playedNote = playedNotes[position]
    if playedNote.getNote() != macroNote.getNote():
        return False
    CHANNEL = playedNote.getChannel()
    VELOCITY = playedNote.getVelocity()
    TIME = playedNote.getTime()
    ELAPSED_TIME = (
        None
        if position == 0
        else playedNote.getTime() - playedNotes[position - 1].getTime()
    )
    c = CHANNEL
    v = VELOCITY
    t = TIME
    et = ELAPSED_TIME
    try:
        result = eval(macroNote.getMatchPredicate())
    except Exception:
        logMatchPredicateEvaluationError(macroNote.getMatchPredicate())
        return False
    return result


def testTriggerWithPlayedNotes(
    playedNotes, triggers, totalNotes=None, start=0, end=None
):
    totalNotes = totalNotes if totalNotes else numNotesInTrigger(triggers)
    end = end if end else len(playedNotes)
    if end - start != totalNotes:
        return False
    position = start
    for trigger in triggers:
        match (trigger):
            case (MacroChord()):
                if not testChordWithMacroChord(playedNotes, position, trigger):
                    return False
            case (MacroNote()):
                if not testNoteWithMacroNote(playedNotes, position, trigger):
                    return False
        position += numNotesInTrigger(trigger)
    return True


def logMatchPredicateEvaluationError(matchPredicate):
    logError(f"failed to evaluate match predicate: {matchPredicate}")
