import unittest
from os.path import pardir, pathsep
from sys import modules

from src.Sampler import Chunk, ChunkProcessor
from src.dictionary.LdxDictionary import LdxBaseDictionary
from src.dictionary.DslDictionary import DslBaseDictionary
from src.filter.ExplainJapaneseSentences import ExplainJapaneseSentences
from src.filter.ExplainKanji import ExplainKanji
from src.filter.PronounceByLetter import PronounceByLetter
from src.filter.StubFinalizer import StubFinalizer
from src.filter.TidyUpEnglish import TidyUpEnglish


class TestDictionaryReaders(unittest.TestCase):
    cache_dir = rf"{modules['src'].__path__[0]}\{pardir}\cache"

    def test_dsl(self):
        dsl = DslBaseDictionary(r'D:\prog\GoldenDict\content\En-Ru-Apresyan.dsl.dz',
                                'utf-16',
                                self.cache_dir)

        for header in {'NAME', 'INDEX_LANGUAGE', 'CONTENTS_LANGUAGE'}:
            self.assertIn(header, dsl.dictionary_header)

        self.assertRegex(dsl.translate_word("'cellist"), r'виолончелист')
        self.assertRegex(dsl.translate_word("clobber"), r'тряпьё')
        self.assertRegex(dsl.translate_word("deliberate"), r'намерен')
        self.assertEqual(len(dsl.get_examples('deliberate')), 13)
        self.assertEqual(len(dsl.get_examples('faux pas')), 1)

    def test_ldx(self):
        dsl = LdxBaseDictionary(r'D:\prog\lingoes\user_data\dict\Vicon English-Russian Dictionary_AB8E9FFF4E1B9B41A60C10CDA8820FD0.ldx',
                                'utf-8',
                                self.cache_dir)

        self.assertEqual(dsl.dictionary_header['type'], 'LDX')
        self.assertRegex(dsl.translate_word("cellist"), r'виолончелист')
        self.assertRegex(dsl.translate_word("clobber"), r'колошматить')
        self.assertRegex(dsl.translate_word("fie"), r'фу')

        dsl = LdxBaseDictionary(r'D:\prog\lingoes\user_data\dict\Vicon English Dictionary_3632FA73AD8738409E3BC214D8B0E91C.ldx',
                                'utf-8',
                                self.cache_dir)

        self.assertEqual(dsl.dictionary_header['type'], 'LDX')
        self.assertRegex(dsl.translate_word('nana'), 'grandmother')
        # self.assertNotRegex(dsl.translate_word('tangerine'), 'rine')

    def test_chunk_preprocessing(self):
        c0 = Chunk(text='"some guy\'s bad text {', language='english', audible=True, printable=True, final=False)
        p0 = ChunkProcessor(filters=[TidyUpEnglish(), StubFinalizer()])
        result = p0.apply_filters(c0)

        c1 = Chunk(text='知りません', language='japanese', audible=False, printable=True, final=False)
        p1 = ChunkProcessor(filters=[ExplainKanji(), StubFinalizer()])
        result = p1.apply_filters(c1)

        c2 = Chunk(text='faux pas', language='english', audible=True, printable=True, final=False)
        p2 = ChunkProcessor(filters=[TidyUpEnglish(), PronounceByLetter(), StubFinalizer()])
        result = p2.apply_filters(c2)

        c3 = Chunk(text='財布の中に何もありません', language='japanese', audible=True, printable=True, final=False)
        p3 = ChunkProcessor(filters=[ExplainJapaneseSentences(), StubFinalizer()])
        result = p3.apply_filters(c3)

        pass


if __name__ == '__main__':
    unittest.main()

