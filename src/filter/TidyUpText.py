from src.filter.BaseFilter import BaseFilter
from re import sub


class TidyUpText(BaseFilter):
    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.final = True
        chunk.text = sub(r"[\\{}]", '', chunk.text)
        return [chunk]
