from aspn import aspn


class MacroNote:
    def __init__(self, note):
        self.note = note
        self.matchPredicates = []
        self.tupleRep = None

    def getNote(self):
        return self.note

    def getMatchPredicates(self):
        return (matchPredicate for matchPredicate in self.matchPredicates)

    def addMatchPredicate(self, matchPredicate):
        self.matchPredicates.append(matchPredicate)
        self.tupleRep = None

    def getTupleRep(self):
        if not self.tupleRep:
            self.tupleRep = (self.note, tuple(self.matchPredicates))
        return self.tupleRep

    def __str__(self):
        matchPredicatesSpecifier = "".join(
            f"{{{matchPredicate}}}" for matchPredicate in self.matchPredicates)
        return f"{aspn.midiNoteToASPN(self.note)}{matchPredicatesSpecifier}"

    def __eq__(self, other):
        if isinstance(other, MacroNote):
            return self.getTupleRep() == other.getTupleRep()
        return False

    def __hash__(self):
        return hash(self.getTupleRep())
