import pickle
from os.path import exists, abspath
from abc import ABC, abstractmethod
from typing import Tuple, List

from src.utils.config import split_name_pair


class BaseDictionary(ABC):

    def __init__(self, file_path, encoding, cache_dir, cache_id_header):
        self.dictionary_data = dict()
        self.dictionary_header = dict()
        self.cache_dir = cache_dir
        self.encoding = encoding
        self.file_path = file_path
        self.cache_id_header = cache_id_header
        self.language_pair = None  # filled by load()
        self.foreign_language, self.native_language = None, None  # filled by load()

    @abstractmethod
    def get_examples(self, word) -> List[Tuple[str, str]]:
        ...

    def get_raw_word_info(self, word):
        word_info = self.dictionary_data.get(word, None)
        return word_info

    @abstractmethod
    def translate_word_chunked(self, word, chunk_factory) -> List:
        ...

    def _save_cache(self):
        dictionary_cache_path = f'{self.cache_dir}/{self.dictionary_header[self.cache_id_header]}.dic'
        with open(dictionary_cache_path, 'wb') as f:
            pickle.dump({"dictionary": self.dictionary_data, "dictionary_header": self.dictionary_header}, f)

    def _load_cache(self) -> bool:
        dictionary_cache_path = f'{self.cache_dir}/{self.dictionary_header[self.cache_id_header]}.dic'
        cache_exists = exists(dictionary_cache_path)
        if cache_exists:
            with open(dictionary_cache_path, 'rb') as f:
                cache = pickle.load(f)
            self.dictionary_data = cache['dictionary']
            self.dictionary_header = cache["dictionary_header"]
        return cache_exists

    @staticmethod
    def load(file_path, dict_type, encoding, language_pair):
        from src.dictionary.DslDictionary import DslBaseDictionary
        from src.dictionary.LdxDictionary import LdxBaseDictionary

        cache_dir = abspath(r'./cache')
        if dict_type == 'dsl':
            dictionary = DslBaseDictionary(file_path, encoding, cache_dir)
        elif dict_type == 'ldx':
            dictionary = LdxBaseDictionary(file_path, encoding, cache_dir)
        else:
            raise Exception('Wrong dictionary type')
        dictionary.language_pair = language_pair
        dictionary.foreign_language, dictionary.native_language = split_name_pair(language_pair)
        return dictionary

    def __getitem__(self, item):
        return self.dictionary_data.get(item, None)
