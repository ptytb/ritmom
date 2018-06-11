from furigana.furigana import split_furigana

from src.Sequencer import Chunk, TextChunk
from src.filter.BaseFilter import BaseFilter


class AddFurigana(BaseFilter):

    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.printable = False
        chunk.final = True

        result = [chunk]
        tokens = self.tokenize(chunk.text)
        for t in tokens:
            result.append(TextChunk(text=t[0], language='japanese', audible=False, printable=True, final=True))
            if len(t) > 1:
                result.append(TextChunk(text=t[1], language='japanese', audible=False, printable=True, final=True))

        return result

    @staticmethod
    def tokenize(text):
        tokens = list(map(list, split_furigana(text)))
        return tokens
        # return ' '.join(list(map(lambda l: l[0] + (f' ({l[1]})' if len(l) > 1 else ''), tokens)))
