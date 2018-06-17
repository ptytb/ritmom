import unittest
from json import load
from os.path import pardir, abspath
from sys import modules

from pathtools.path import parent_dir_path

from src.PhraseExamples import PhraseExamples
from src.dictionary.LdxDictionary import LdxBaseDictionary
from src.dictionary.DslDictionary import DslBaseDictionary
from src.filter.AddFurigana import AddFurigana
from src.filter.ExpandContractions import ExpandContractions
from src.filter.ExplainJapaneseSentences import ExplainJapaneseSentences
from src.filter.ExplainKanji import ExplainKanji
from src.filter.PronounceByLetter import PronounceByLetter
from src.filter.SimilarKanji import jp_reverse
from src.filter.SplitMixedLanguages import SplitMixedLanguages
from src.filter.StubFinalizer import StubFinalizer
from src.filter.TidyUpEnglish import TidyUpEnglish
from src.filter.TidyUpText import TidyUpText

from src.utils.config import split_name_pair


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
        from src.Sequencer import ChunkProcessor, TextChunk

        c0 = TextChunk(text='"some guy\'s bad text {', language='english', audible=True, printable=True, final=False)
        p0 = ChunkProcessor(filters=[TidyUpEnglish(), StubFinalizer()])
        result0 = p0.apply_filters(c0)

        c1 = TextChunk(text='知りません', language='japanese', audible=False, printable=True, final=False)
        p1 = ChunkProcessor(filters=[ExplainKanji(), StubFinalizer()])
        result1 = p1.apply_filters(c1)

        c2 = TextChunk(text='faux pas', language='english', audible=True, printable=True, final=False)
        p2 = ChunkProcessor(filters=[PronounceByLetter(), StubFinalizer()])
        result2 = p2.apply_filters(c2)

        c3 = TextChunk(text='財布の中に何もありません', language='japanese', audible=True, printable=True, final=False)
        p3 = ChunkProcessor(filters=[ExplainJapaneseSentences(), StubFinalizer()])
        result3 = p3.apply_filters(c3)

        c4 = TextChunk(text='財布の中に何もありません', language='japanese', audible=True, printable=True, final=False)
        p4 = ChunkProcessor(filters=[AddFurigana(), StubFinalizer()])
        result4 = p4.apply_filters(c4)

        r = jp_reverse('知')
        
        c5 = TextChunk(text='/in brackets/some_bad_formatting{going}here()', language='japanese', audible=True, printable=True, final=False)
        p5 = ChunkProcessor(filters=[TidyUpText(), StubFinalizer()])
        result5 = p5.apply_filters(c5)

        pass

    def test_split(self):
        a, b = split_name_pair('EnglishJapanese')
        self.assertEqual(a, 'english')
        self.assertEqual(b, 'japanese')

    def test_promote(self):
        from src.Sequencer import TextChunk, SpeechChunk
        a = TextChunk(text='財布の中に何もありません', language='japanese', audible=True, printable=True, final=False)
        b = a.promote(SpeechChunk, volume=75)

    def test_examples(self):
        ritmom_root = parent_dir_path(parent_dir_path(abspath(__file__)))

        with open(f'{ritmom_root}/config.json') as f:
            config = load(f)
        pe = PhraseExamples(config)
        wi = pe.get_definitions_and_examples('stand up', 'english')

        # print(list(wi.definitions))
        # print(list(wi.antonyms))
        # print(list(wi.synonyms))
        # print(list(wi.examples))
        pass
        
    def test_abbr(self):
        from src.Sequencer import TextChunk, ChunkProcessor
        a = TextChunk(text='to listen up to smb. and smth.', language='english', audible=True, printable=True, final=False)
        p0 = ChunkProcessor(filters=[ExpandContractions(), StubFinalizer()])
        result = p0.apply_filters(a)
        assert all(map(lambda s: s in result[0].text, ['somebody', 'something']))
        
    def test_split_mixed_languages(self):
        from src.Sequencer import TextChunk, ChunkProcessor
        a = TextChunk(text='hi there привет こんにちは', language='english', audible=True, printable=True, final=False)
        p0 = ChunkProcessor(filters=[SplitMixedLanguages(), StubFinalizer()])
        result = p0.apply_filters(a)
        assert result[0].language == 'english'
        assert result[1].language == 'russian'
        assert result[2].language == 'japanese'


if __name__ == '__main__':
    unittest.main()

