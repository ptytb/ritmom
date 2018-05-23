from os.path import abspath

import sys
sys.path.append('..')

import translate
from translate.DslDictionary import DslDictionary


class TextSource:
    def __init__(self, source):
        self.source = abspath(source)
        self.dictionary = DslDictionary('D:\prog\GoldenDict\content\En-Ru-Apresyan.dsl.dz',
                                        'utf-16',
                                        r'D:\work\Python\ritmom\cache')

    def __iter__(self):
        return self

    def __next__(self):
        with open(self.source, newline='', errors='replace', encoding='utf-8') as f:
            while True:
                line = f.readline()
                if line == '':
                    continue
                if line is None:
                    break
                word = line.strip()
                trans = self.dictionary.translate_word(word)
                yield word, trans
