from collections import deque
from typing import Deque, List
import attr

from src.filter import BaseFilter


def make_range_validator(low, high):
    def validate(instance, attribute, value):
        if not low <= value <= high:
            raise ValueError(f'{instance}: {attribute}={value}')
    return validate


@attr.s
class Chunk:
    text = attr.ib(type=str, default=None)
    language = attr.ib(type=str, default=None)
    audible = attr.ib(type=bool, default=True)
    printable = attr.ib(type=bool, default=True)
    final = attr.ib(type=bool, default=False)  # Whether chunk can be filtered to let derived chunks be generated


@attr.s
class AudioChunk(Chunk):
    volume = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                          make_range_validator(0, 100)],
                     default=50)
    rate = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                        make_range_validator(-10, 10)],
                   default=0)


@attr.s
class SpeechChunk(AudioChunk):
    voice = attr.ib(type=str, default=None)


@attr.s
class JingleChunk(AudioChunk):
    jingle = attr.ib(type=str, default=None)


class ChunkProcessor:
    def __init__(self, filters=list()):
        self.filters: List[BaseFilter] = filters

    def apply_filters(self, chunk: Chunk) -> List[Chunk]:
        result = [chunk]
        result_is_not_final = True

        while result_is_not_final:
            for f in self.filters:
                new_result = list()
                for chunk in result:
                    new_result.extend([chunk] if chunk.final else f(chunk))
                result = new_result
            result_is_not_final = any(map(lambda c: not c.final, result))

        return result


class Sampler:
    def __init__(self):
        self.queue: Deque[Chunk] = deque()
        self.chunk_processor = ChunkProcessor()

    def append(self, chunk: Chunk):
        self.queue.extendleft(self.chunk_processor.apply_filters(chunk))

    def pop(self):
        return self.queue.pop()
