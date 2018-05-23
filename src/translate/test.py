import unittest
from .DslDictionary import DslDictionary


class TestDictionaryReaders(unittest.TestCase):
    
    def test_dsl(self):
        dsl = DslDictionary(r'D:\prog\GoldenDict\content\En-Ru-Apresyan.dsl.dz', 'utf-16', r'D:\work\Python\ritmom\cache')
        # dsl = DslDictionary(r'D:\work\Python\ritmom\src\translate\En-Ru-Apresyan.dsl.gz', 'utf-16', r'D:\work\Python\ritmom\cache')

        for header in {'NAME', 'INDEX_LANGUAGE', 'CONTENTS_LANGUAGE'}:
            self.assertIn(header, dsl.dictionary_header)

        self.assertRegex(dsl.translate_word("'cellist"), r'виолончелист')


if __name__ == '__main__':
    unittest.main()

