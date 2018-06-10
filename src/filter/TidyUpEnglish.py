from src.filter.BaseFilter import BaseFilter
from re import sub


class TidyUpEnglish(BaseFilter):
    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.text = sub(r"^['`\"]+|['`\"]+$", '', chunk.text)
        return [chunk]
