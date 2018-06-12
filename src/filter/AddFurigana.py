from furigana.furigana import split_furigana

from src.filter.BaseFilter import BaseFilter


class AddFurigana(BaseFilter):

    def __call__(self, chunk):
        from src.Sequencer import TextChunk

        chunk = self._duplicate_chunk(chunk)
        result = [chunk]

        if isinstance(chunk, TextChunk) and chunk.language == 'japanese':
            chunk.printable = False
            tokens = self.tokenize(chunk.text)
            for t in tokens:
                result.append(TextChunk(text=t[0], language='japanese', audible=False, printable=True, final=True))
                if len(t) > 1:
                    text = f' ({t[1]}) '
                    result.append(TextChunk(text=text, language='japanese', audible=False, printable=True, final=True))

        return result

    @staticmethod
    def tokenize(text):
        tokens = map(list, split_furigana(text))
        return tokens
