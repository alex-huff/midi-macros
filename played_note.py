class PlayedNote:
    def __init__(self, note, velocity, time):
        self.note = note
        self.velocity = velocity
        self.time = time

    def getNote(self):
        return self.note

    def getVelocity(self):
        return self.velocity

    def getTime(self):
        return self.time
