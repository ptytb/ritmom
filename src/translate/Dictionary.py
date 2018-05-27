import pickle
from os.path import exists, abspath


class Dictionary:

    def __init__(self, file_path, encoding, cache_dir, cache_id_header):
        self.dictionary_data = dict()
        self.dictionary_header = dict()
        self.cache_dir = cache_dir
        self.encoding = encoding
        self.file_path = file_path
        self.cache_id_header = cache_id_header

    def translate_word(self, word):
        trans = self.dictionary_data.get(word, None)
        if trans is None:
            return trans
        return self._filter_formatting(trans)

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
    def load(file_path, dict_type, encoding):
        from src.translate.DslDictionary import DslDictionary
        from src.translate.LdxDictionary import LdxDictionary

        cache_dir = abspath(r'./cache')
        if dict_type == 'dsl':
            return DslDictionary(file_path, encoding, cache_dir)
        elif dict_type == 'ldx':
            return LdxDictionary(file_path, encoding, cache_dir)
        else:
            raise Exception('Wrong dictionary type')

    @staticmethod
    def _filter_formatting(text):
        pass

