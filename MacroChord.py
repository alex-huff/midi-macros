class MacroChord:
    def __init__(self, chord, matchPredicate):
        self.chord = chord
        self.matchPredicate = matchPredicate

    def getChord(self):
        return self.chord

    def getMatchPredicate(self):
        return self.matchPredicate

    def tupleRep(self):
        return (self.chord, self.matchPredicate)

    def __str__(self):
        matchPredicateString = f'{{{self.matchPredicate}}}' if self.matchPredicate != 'True' else ''
        return f'({"|".join(str(note) for note in self.chord)}){matchPredicateString}'

    def __eq__(self, other):
        if (isinstance(other, MacroChord)):
            return self.tupleRep() == other.tupleRep()
        return False

    def __hash__(self):
        return hash(self.tupleRep())
