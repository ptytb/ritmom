class UnrollMultilineCell:
    def __init__(self, default_language):
        self.default_language = default_language

    def __call__(self, lines):
        """
        Decorator splits multiline cells into separate rows

        :param gen_lines_func: a function returning rows (possibly with multiline cells) from source
        :return: a function returning tuple: LanguagePair, foreign word, translation to native
        """
        def lines_func():
            while True:
                line = next(lines)
                language_pair = f'{line[0]}{line[1]}' if len(line) > 2 else self.default_language
                if len(line) == 2:
                    foreign, native = line
                else:
                    foreign, native = line[2:4]
                if '\n' in foreign:
                    pairs = zip(foreign.split('\n'), native.split('\n'))
                    for pair in pairs:
                        yield (language_pair, *pair)
                else:
                    yield language_pair, foreign, native

        return lines_func()

