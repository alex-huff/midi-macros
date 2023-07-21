class ParseError(Exception):
    def __init__(self, message, parseBuffer):
        self.message = message
        self.parseBuffer = parseBuffer

    def getSourceString(self):
        position = self.parseBuffer.at()
        return f"source: <{self.parseBuffer.source}>, position:{position[0] + 1},{position[1] + 1}"
