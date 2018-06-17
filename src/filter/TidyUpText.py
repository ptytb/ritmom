from src.filter.BaseFilter import BaseFilter
from re import sub


class TidyUpText(BaseFilter):
    
    def __init__(self):
        super().__init__()

    def __call__(self, chunk):
        from src.Sequencer import TextChunk
        chunk = self._duplicate_chunk(chunk)
        if isinstance(chunk, TextChunk):
            chunk.text = sub(r'[\\{}]', ' ', chunk.text)
            chunk.text = sub(r'/(.*?)/', r'(\1)', chunk.text)
            chunk.text = sub(r'[/]', '', chunk.text)
            chunk.text = sub(r'_', ' ', chunk.text)
            chunk.text = sub(r'\(\s*\)', ' ', chunk.text)
            chunk.text = sub(r'\s+', ' ', chunk.text)
            chunk.text = sub(r'^\s+|\s+$', '', chunk.text)
        return [chunk]
