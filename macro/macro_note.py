from aspn import aspn


class MacroNote:
    def __init__(self, note, matchPredicate):
        self.note = note
        self.matchPredicate = matchPredicate

    def getNote(self):
        return self.note

    def getMatchPredicate(self):
        return self.matchPredicate

    def tupleRep(self):
        return (self.note, self.matchPredicate)

    def __str__(self):
        matchPredicateString = f'{{{self.matchPredicate}}}' if self.matchPredicate != 'True' else ''
        return f'{aspn.midiNoteToASPN(self.note)}{matchPredicateString}'

    def __eq__(self, other):
        if (isinstance(other, MacroNote)):
            return self.tupleRep() == other.tupleRep()
        return False

    def __hash__(self):
        return hash(self.tupleRep())
