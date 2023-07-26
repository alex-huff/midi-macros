class MacroChord:
    def __init__(self, chord):
        self.chord = chord
        self.matchPredicates = []
        self.tupleRep = None

    def getChord(self):
        return self.chord

    def getMatchPredicates(self):
        return (matchPredicate for matchPredicate in self.matchPredicates)

    def addMatchPredicate(self, matchPredicate):
        self.matchPredicates.append(matchPredicate)
        self.tupleRep = None

    def getTupleRep(self):
        if not self.tupleRep:
            self.tupleRep = (self.chord, tuple(self.matchPredicates))
        return self.tupleRep

    def __str__(self):
        matchPredicatesSpecifier = "".join(
            f"{{{matchPredicate}}}" for matchPredicate in self.matchPredicates)
        return f'[{"|".join(str(note) for note in self.chord)}]{matchPredicatesSpecifier}'

    def __eq__(self, other):
        if isinstance(other, MacroChord):
            return self.getTupleRep() == other.getTupleRep()
        return False

    def __hash__(self):
        return hash(self.getTupleRep())
