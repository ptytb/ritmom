from collections import deque, Iterable
from typing import Deque, List
import attr

from src.filter.AddFurigana import AddFurigana
from src.filter.AddVoice import AddVoice
from src.filter.BaseFilter import BaseFilter
from src.filter.ExplainKanji import ExplainKanji
from src.filter.PronounceByLetter import PronounceByLetter
from src.filter.StubFinalizer import StubFinalizer
from src.utils.lists import flatten
from src.filter.TidyUpText import TidyUpText
from src.filter.SplitMixedLanguages import SplitMixedLanguages


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
class ControlChunk(Chunk):
    ...


@attr.s
class FilterControlChunk(ControlChunk):
    instant = attr.ib(type=bool)
    target = attr.ib(type=BaseFilter)  # Which filter we want to control
    attribute = attr.ib(type=str)
    value = attr.ib()
    audible = attr.ib(type=bool, default=False)
    printable = attr.ib(type=bool, default=False)
    final = attr.ib(type=bool, default=True)


@attr.s
class TextChunk(Chunk):
    text = attr.ib(type=str, default=None)
    language = attr.ib(type=str, default=None)


@attr.s
class AudioChunkMixin:
    volume = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                          make_range_validator(0, 100)],
                     default=50)
    rate = attr.ib(type=int, validator=[attr.validators.instance_of(int),
                                        make_range_validator(-10, 10)],
                   default=0)


@attr.s(repr=False)
class SpeechChunk(AudioChunkMixin, TextChunk):
    voice = attr.ib(default=None)
    
    def __repr__(self):
        return self.voice.Id.rpartition('\\')[-1]


@attr.s
class JingleChunk(AudioChunkMixin, Chunk):
    jingle = attr.ib(type=str, default=None)
    final = attr.ib(type=bool, default=True)


class ChunkProcessor:
    def __init__(self, filters=list()):
        self.filters = filters

    def apply_filters(self, chunk: Chunk) -> List[Chunk]:
        result = [chunk]
        result_is_final = chunk.final

        while not result_is_final:
            for f in self.filters:
                if not f.enabled:
                    continue
                new_result = list()
                for chunk in result:
                    new_result.extend([chunk] if chunk.final or not isinstance(chunk, TextChunk) else f(chunk))
                result = new_result
            result_is_final = all(map(lambda c: c.final, result))

        return result


class Sequencer:
    def __init__(self):
        self.queue: Deque[Chunk] = deque()
        self.chunk_processor = ChunkProcessor(filters=[
            TidyUpText(),
            SplitMixedLanguages(),
            PronounceByLetter(),
            AddFurigana(),
            ExplainKanji(),
            AddVoice(),
            StubFinalizer()
        ])
    
    def __lshift__(self, chunk):
        self.append(chunk)
        return self
    
    def _apply_control_chunk(self, chunk: ControlChunk):
        if isinstance(chunk, FilterControlChunk) and issubclass(chunk.target, BaseFilter):
            for f in self.chunk_processor.filters:
                if isinstance(f, chunk.target):
                    setattr(f, chunk.attribute, chunk.value)

    def append(self, chunk: Chunk):
        if isinstance(chunk, ControlChunk):
            if chunk.instant:
                self._apply_control_chunk(chunk)
            else:
                self.queue.appendleft(chunk)
            return
        flat = flatten([attr.evolve(chunk)])  # copy as an alternative to immutability
        for chunk in flat:
            filtered = self.chunk_processor.apply_filters(chunk)
            self.queue.extendleft(filtered)

    def __len__(self):
        return len(self.queue)

    def pop(self):
        chunk = self.queue.pop()
        if isinstance(chunk, ControlChunk):
            self._apply_control_chunk(chunk)
            chunk = None
        return chunk
