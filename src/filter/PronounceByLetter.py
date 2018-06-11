from src.filter.BaseFilter import BaseFilter
from re import search


class PronounceByLetter(BaseFilter):

    def __call__(self, chunk):
        from src.Sequencer import JingleChunk, TextChunk

        chunk = self._duplicate_chunk(chunk)
        chunk.final = True
        result = [chunk]

        if self._needs_process(chunk.text, chunk.language):
            result.append(JingleChunk(jingle='silence_long', printable=False))
            result.append(JingleChunk(jingle='by_letter', printable=False))
            result.append(JingleChunk(jingle='silence', printable=False))
            for letter in chunk.text:
                result.append(JingleChunk(jingle='silence', printable=False))
                if letter.isspace():
                    result.append(JingleChunk(jingle='space', printable=False))
                else:
                    result.append(TextChunk(text=letter, language='english',
                                            audible=True, printable=False, final=True))
        return result

    @staticmethod
    def _needs_process(text, language):
        """
        Tests if a word should be pronounced by letter
        """
        patterns = {
            'english': [
                'x',
                'ru',
                'bu',
                'eu',
                'au',
                'c[eiy]',
                'ei',
                'ou',
                'ow',
                'aw',
                'kn',
                'e$',
                'iae'
            ]
        }

        def test_func(pattern):
            return search(pattern, text)

        return language in patterns and any(map(test_func, patterns[language]))
