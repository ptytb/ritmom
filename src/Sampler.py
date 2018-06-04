from collections import deque
from typing import Deque, List

from .filter import BaseFilter


class Chunk:
    ...


class JingleChunk(Chunk):
    ...


class TextChunk(Chunk):
    def __init__(self, text, language, filters=list()):
        self.text = text
        self.language = language
        self.filters: List[BaseFilter] = filters

    def _apply_filters(self, printable: bool):
        result = self.text
        for f in self.filters:
            result = f.apply(result, printable=printable)
        return result

    def get_printable(self):
        return self._apply_filters(printable=True)

    def get_audible(self):
        return self._apply_filters(printable=False)


class Sampler:
    def __init__(self):
        self.queue: Deque[TextChunk] = deque()

    def append(self, chunk: TextChunk):
        self.queue.appendleft(chunk)

    def pop(self):
        return self.queue.pop()
