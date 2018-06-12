from src.filter.BaseFilter import BaseFilter


class StubFinalizer(BaseFilter):
    
    def __init__(self):
        super().__init__()

    def __call__(self, chunk):
        self._duplicate_chunk(chunk)
        chunk.final = True
        return [chunk]
