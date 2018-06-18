from functools import partial
from typing import List, Dict

from src.Sequencer import TextChunk, JingleChunk
from src.dictionary.BaseDictionary import BaseDictionary
from src.utils.singleton import Singleton


class Translator(metaclass=Singleton):

    # @classmethod
    # def __new__(cls, *args, **kwargs):
    #     if not hasattr(cls, 'instance'):
    #         cls.instance = super(Translator, cls).__new__(cls)
    #     return cls.instance

    def __init__(self, dict_descriptors):
        if dict_descriptors is None:
            return

        self.dictionaries: Dict[str, List[BaseDictionary]] = dict()
        self.all_dictionaries: List[BaseDictionary] = list()
        self._load_dictionaries(dict_descriptors)

    def _load_dictionaries(self, dict_descriptors):
        for d in dict_descriptors:
            language_pair = d['pair']
            dictionary = BaseDictionary.load(d['file'], d['type'], d['encoding'], language_pair)

            if language_pair not in self.dictionaries:
                self.dictionaries[language_pair] = list()

            self.dictionaries[language_pair].append(dictionary)
            self.all_dictionaries.append(dictionary)

    def translate(self, word, language_pair=None):
        def chunk_factory(*, language, text):
            return TextChunk(text=text, language=language)

        if language_pair and language_pair in self.dictionaries:
            dictionaries = self.dictionaries[language_pair]
        else:
            dictionaries = self.all_dictionaries

        result = list()

        for d in dictionaries:
            chunks = d.translate_word_chunked(word, chunk_factory)
            if chunks:
                result.extend(chunks)

        return result

    def get_examples(self, word, language):

        def example_sequence(foreign, native, pair):
            return [
                TextChunk(text=pair[0].strip(), language=foreign),
                JingleChunk(jingle='silence'),
                TextChunk(text=pair[1].strip(), language=native)
            ]

        examples = list()
        for d in self.all_dictionaries:
            if d.language_pair.startswith(language.capitalize()):
                to_chunks = partial(example_sequence, d.foreign_language, d.native_language)
                examples += map(to_chunks, d.get_examples(word))

        return examples
