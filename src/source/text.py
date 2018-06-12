from os.path import abspath

from src.Translator import Translator


class TextSource:
    def __init__(self, source, language_pair):
        self.source = abspath(source)
        self.translator = Translator(None)
        self.language_pair = language_pair

    def __iter__(self):
        return self

    def __next__(self):
        with open(self.source, 'rt', errors='replace', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line == '':
                    continue
                trans = self.translator.translate(line, self.language_pair)
                yield line, trans
