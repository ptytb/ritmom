
from furigana.furigana import split_furigana


def process(text):
    tokens = list(map(list, split_furigana(text)))
    return ' '.join(list(map(lambda l: l[0] + (f' ({l[1]})' if len(l) > 1 else ''), tokens)))
