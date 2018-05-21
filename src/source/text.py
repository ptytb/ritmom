from os.path import abspath


class TextSource:
    def __init__(self, source):
        self.source = abspath(source)

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
                trans = ''
                yield word, trans
