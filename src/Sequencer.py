from collections import deque, Iterable
from copy import deepcopy, copy
from typing import Deque, List
import attr

from src.filter import BaseFilter
from src.utils.lists import flatten


def make_range_validator(low, high):
    def validate(instance, attribute, value):
        if not low <= value <= high:
            raise ValueError(f'{instance}: {attribute}={value}')
    return validate


def as_chunks(items: Iterable, language, prepend: List, append: List = list()):
    for item in items:
        yield from prepend
        yield TextChunk(text=item, language=language)
        yield from append


@attr.s
class Chunk:
    audible = attr.ib(type=bool, default=True)
    printable = attr.ib(type=bool, default=True)
    final = attr.ib(type=bool, default=False)  # Whether chunk can be filtered to let derived chunks be generated

    def promote(self, target_class, **changes):
        assert issubclass(target_class, self.__class__)
        cls = target_class
        attributes = attr.fields(cls)
        for a in attributes:
            if not a.init:
                continue
            attr_name = a.name  # To deal with private attributes.
            init_name = attr_name if attr_name[0] != "_" else attr_name[1:]
            if init_name not in changes:
                changes[init_name] = getattr(self, attr_name, a.default)
        return cls(**changes)


@attr.s
class TextChunk(Chunk):
    text = attr.ib(type=str, default=None)
    language = attr.ib(type=str, default=None)


@attr.s
class AudioChunk(Chunk):
    volume = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                          make_range_validator(0, 100)],
                     default=50)
    rate = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                        make_range_validator(-10, 10)],
                   default=0)


@attr.s
class SpeechChunk(AudioChunk, TextChunk):
    voice = attr.ib(default=None)
    final = attr.ib(type=bool, default=True)


@attr.s
class JingleChunk(AudioChunk):
    jingle = attr.ib(type=str, default=None)
    final = attr.ib(type=bool, default=True)


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


class Sequencer:
    def __init__(self):
        self.queue: Deque[Chunk] = deque()
        self.chunk_processor = ChunkProcessor()

    def append(self, chunk: Chunk):
        flat = flatten([attr.evolve(chunk)])  # copy as an alternative to immutability
        for chunk in flat:
            self.queue.extendleft(self.chunk_processor.apply_filters(chunk))

    def __len__(self):
        return len(self.queue)

    def pop(self):
        return self.queue.pop()
