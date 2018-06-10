import jaconv
import sys

from src.Sampler import Chunk

sys.__stdout__ = sys.stdout
from cihai.core import Cihai
from cihai.bootstrap import bootstrap_unihan

from src.filter.BaseFilter import BaseFilter


class ExplainKanji(BaseFilter):
    def __init__(self):
        self.c = Cihai()

        if not self.c.is_bootstrapped:  # download and install Unihan to db
            bootstrap_unihan(self.c.metadata)
            self.c.reflect_db()

    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.final = True
        result = [chunk]

        explanations = self._get_explanations(chunk.text)

        for k, on, kun, explanation in explanations:
            result.append(Chunk(text=k, language='japanese', audible=False, printable=True, final=True))
            result.append(Chunk(text='on', language='english', audible=True, printable=False, final=True))
            result.append(Chunk(text=on, language='japanese', audible=True, printable=True, final=True))
            result.append(Chunk(text='koon', language='english', audible=True, printable=False, final=True))
            result.append(Chunk(text=kun, language='japanese', audible=True, printable=True, final=True))
            result.append(Chunk(text=explanation, language='english', audible=True, printable=True, final=True))

        return result

    def _kanji_to_kana(self, char):
        glyph = self.c.lookup_char(char).first()
        if glyph is None:
            return None
        romaji_on = glyph.kJapaneseKun.lower()
        romaji_kun = glyph.kJapaneseOn.lower()
        jp_on = jaconv.alphabet2kana(romaji_on).split(' ')
        jp_kun = jaconv.hira2kata(jaconv.alphabet2kana(romaji_kun)).split(' ')
        return jp_on, jp_kun, glyph.kDefinition

    @staticmethod
    def is_kana(char):
        return ('\u30A0' <= char <= '\u30FF') or ('\u3040' <= char <= '\u309F')  # Katakana and Hiragana blocks

    @classmethod
    def is_kanji(cls, char):
        return not cls.is_kana(char)

    def _get_explanations(self, text):
        kanji = set(filter(self.is_kanji, text))
        detail_list = []
        for k in kanji:
            triplet = self._kanji_to_kana(k)
            if triplet is None:
                continue
            on, kun, definition = triplet
            # detail_list.append(f'{k}: {", ".join(on)}; {", ".join(kun)}; {definition}')
            detail_list.append((k, on, kun, definition))
        return detail_list
