import unittest
from os.path import pardir, pathsep
from sys import modules

from src.translate.LdxDictionary import LdxDictionary
from src.translate.DslDictionary import DslDictionary


class TestDictionaryReaders(unittest.TestCase):
    cache_dir = rf"{modules['src'].__path__[0]}\{pardir}\cache"

    def test_dsl(self):
        dsl = DslDictionary(r'D:\prog\GoldenDict\content\En-Ru-Apresyan.dsl.dz',
                            'utf-16',
                            self.cache_dir)

        for header in {'NAME', 'INDEX_LANGUAGE', 'CONTENTS_LANGUAGE'}:
            self.assertIn(header, dsl.dictionary_header)

        self.assertRegex(dsl.translate_word("'cellist"), r'виолончелист')
        self.assertRegex(dsl.translate_word("clobber"), r'тряпьё')

    def test_ldx(self):
        dsl = LdxDictionary(r'D:\prog\lingoes\user_data\dict\Vicon English-Russian Dictionary_AB8E9FFF4E1B9B41A60C10CDA8820FD0.ldx',
                            'utf-8',
                            self.cache_dir)

        self.assertEqual(dsl.dictionary_header['type'], 'LDX')
        self.assertRegex(dsl.translate_word("cellist"), r'виолончелист')
        self.assertRegex(dsl.translate_word("clobber"), r'колошматить')
        self.assertRegex(dsl.translate_word("fie"), r'фу')


if __name__ == '__main__':
    unittest.main()

