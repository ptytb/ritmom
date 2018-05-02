import jaconv
import sys
sys.__stdout__ = sys.stdout
from cihai.core import Cihai
from cihai.bootstrap import bootstrap_unihan


c = Cihai()

if not c.is_bootstrapped:  # download and install Unihan to db
    bootstrap_unihan(c.metadata)
    c.reflect_db()


def kanji_to_kana(char):
    glyph = c.lookup_char(char).first()
    if glyph is None:
        return None
    romaji_on = glyph.kJapaneseKun.lower()
    romaji_kun = glyph.kJapaneseOn.lower()
    jp_on = jaconv.alphabet2kana(romaji_on).split(' ')
    jp_kun = jaconv.hira2kata(jaconv.alphabet2kana(romaji_kun)).split(' ')
    return jp_on, jp_kun, glyph.kDefinition


def is_kana(char):
    return ('\u30A0' <= char <= '\u30FF') or ('\u3040' <= char <= '\u309F')  # Katakana and Hiragana blocks


def is_kanji(char):
    return not is_kana(char)


def process(text):
    kanji = set(filter(is_kanji, text))
    detail_list = []
    for k in kanji:
        triplet = kanji_to_kana(k)
        if triplet is None:
            continue
        on, kun, definition = triplet
        detail_list.append(f'{k}: {", ".join(on)}; {", ".join(kun)}; {definition}')
    return '\n'.join(detail_list)
