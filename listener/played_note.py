from aspn.aspn import midiNoteToASPN


class PlayedNote:
    def __init__(self, note, channel, velocity, time):
        self.note = note
        self.channel = channel
        self.velocity = velocity
        self.time = time

    def getNote(self):
        return self.note

    def getASPN(self):
        return midiNoteToASPN(self.note, unicode=False)

    def getChannel(self):
        return self.channel

    def getVelocity(self):
        return self.velocity

    def getTime(self):
        return self.time
