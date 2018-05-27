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
        with open(self.source, 'rt', newline='', errors='replace', encoding='utf-8') as f:
            for line in f:
                if line == '':
                    continue
                word = line.strip()
                trans = self.translator.translate(word, self.language_pair)
                yield word, trans
