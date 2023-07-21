from parser.parse_error import ParseError


class ParseBuffer:
    def __init__(self, lines, source, commentChar="#"):
        self.lines = lines
        self.source = source
        self.commentChar = commentChar
        if not self.lines:
            raise ValueError("lines is empty")
        self.currentLineNumber = 0
        self.currentLine = self.lines[self.currentLineNumber]
        self.positionInLine = 0
        self.skipTillData()

    def __str__(self):
        return self.currentLine

    def __len__(self):
        return len(self.currentLine)

    def __getitem__(self, key):
        try:
            return self.currentLine.__getitem__(key)
        except IndexError:
            self.jump((self.currentLineNumber, len(self)))
            raise ParseError(
                f'unexpectedly reached end of line.\n{self.currentLine}\n{" " * len(self) + "^"}',
                self
            )

    def at(self):
        return (self.currentLineNumber, self.positionInLine)

    def getCurrentLine(self):
        return self.currentLine

    def getCurrentChar(self):
        return self[self.positionInLine]

    def skip(self, number):
        self.positionInLine += number

    def jump(self, position):
        lineNumber, positionInLine = position
        self.currentLineNumber = lineNumber
        self.currentLine = self.lines[self.currentLineNumber]
        self.positionInLine = positionInLine

    def skipComment(self):
        self.eatWhitespace()
        if (
            self.positionInLine < len(self)
            and self.getCurrentChar() == self.commentChar
        ):
            self.positionInLine = len(self)

    def skipTillData(self):
        self.skipComment()
        while (
            self.positionInLine == len(self)
            and self.currentLineNumber < len(self.lines) - 1
        ):
            self.newline()
            self.skipComment()

    def atEndOfLine(self):
        return self.positionInLine == len(self)

    def atEndOfBuffer(self):
        return self.currentLineNumber == len(self.lines) - 1 and self.atEndOfLine()

    def stringFrom(self, startPosition, endPosition):
        lines = []
        if not startPosition:
            startPosition = (0, 0)
        if not endPosition:
            endPosition = (len(self.lines) - 1, len(self.lines[-1]))
        startLine, endLine = startPosition[0], endPosition[0]
        startPositionInLine, endPositionInLine = startPosition[1], endPosition[1]
        if startLine == endLine:
            return self.lines[startLine][startPositionInLine:endPositionInLine]
        lines.append(self.lines[startLine][startPositionInLine:])
        for lineNumber in range(startLine + 1, endLine):
            lines.append(self.lines[lineNumber])
        lines.append(self.lines[endLine][:endPositionInLine])
        return "\n".join(lines)

    def eatWhitespace(self):
        while self.positionInLine < len(self) and self.getCurrentChar().isspace():
            self.positionInLine += 1

    def newline(self):
        self.currentLineNumber += 1
        self.currentLine = self.lines[self.currentLineNumber]
        self.positionInLine = 0
