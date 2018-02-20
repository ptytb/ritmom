import jaconv
import sys
sys.__stdout__ = sys.stdout
from cihai.core import Cihai
from cihai.bootstrap import bootstrap_unihan


c = Cihai()


if not c.is_bootstrapped:  # download and install Unihan to db
    bootstrap_unihan(c.metadata)
    c.reflect_db()


def jp_reverse(word):
    query = c.reverse_char(word)
    return ', '.join([glyph.char for glyph in query])
