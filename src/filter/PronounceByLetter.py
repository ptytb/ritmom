from src.Sampler import Chunk, JingleChunk
from src.filter.BaseFilter import BaseFilter
from re import search


class PronounceByLetter(BaseFilter):

    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        result = [chunk]
        if self._needs_process(chunk.text, chunk.language):
            result.append(JingleChunk(jingle='by_letters'))
            for letter in chunk.text:
                if letter.isspace():
                    result.append(JingleChunk(jingle='space'))
                else:
                    result.append(Chunk(text=letter, language='english', audible=True, printable=False, final=True))
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
