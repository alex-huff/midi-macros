from parser.parse_error import ParseError

class ParseBuffer(str):
    def __getitem__(self, key):
        try:
            return ParseBuffer(str.__getitem__(self, key))
        except IndexError:
            raise ParseError(
                f'unexpectedly reached end of line.\n{self}\n{" " * len(self) + "^"}'
            )
