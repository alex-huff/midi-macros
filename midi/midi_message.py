class MIDIMessage:
    def __init__(self, message):
        self.message = message
        assert len(self.message) > 0
        self.data_0 = self.message[0]
        self.data_1 = self.message[1] if len(self.message) > 1 else None
        self.data_2 = self.message[2] if len(self.message) > 2 else None
        self.status = self.data_0 >> 4
        self.channel = self.data_0 & 0xF

    def getMessage(self):
        return self.message

    def getData0(self):
        return self.data_0

    def getData1(self):
        return self.data_1

    def getData2(self):
        return self.data_2

    def getStatus(self):
        return self.status

    def getChannel(self):
        return self.channel
