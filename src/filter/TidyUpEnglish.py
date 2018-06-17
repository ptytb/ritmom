from src.filter.BaseFilter import BaseFilter
from re import sub


class TidyUpEnglish(BaseFilter):
    
    def __init__(self):
        super().__init__()

    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.final = True
        if chunk.language == 'english':
            chunk.text = sub(r"^['`\"]+|['`\"]+$", '', chunk.text)
            chunk.text = sub(r"\s+'\s+", "'", chunk.text)
        return [chunk]
