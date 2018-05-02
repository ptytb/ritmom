import pickle
from genericpath import exists

import nltk
from nltk import ConcordanceIndex


class WordNetCache:
    _lock = None

    @classmethod
    def get_lock(cls):
        return cls._lock

    def __init__(self, _app_config):
        self.app_config = _app_config
        self._byLanguage = dict()
        self._lock = self.get_lock()

    @staticmethod
    def key_func(s):
        return s.lower()

    def get_cache(self, language):
        if language not in self._byLanguage:
            self._byLanguage[language] = dict()
            self._byLanguage[language]['texts'] = dict()
            self._byLanguage[language]['indices'] = dict()
            with self.get_lock():
                if exists(f'cache/{language}.ready'):
                    self._load_cache(language)
                else:
                    corpus_names = self.app_config['phraseExamples'][language]
                    for corpus_name in corpus_names:
                        corpus = getattr(nltk.corpus, corpus_name)
                        text = self._byLanguage[language]['texts'][corpus_name] = nltk.Text(corpus.words())
                        self._byLanguage[language]['indices'][corpus_name] = ConcordanceIndex(text.tokens,
                                                                                              key=self.key_func)
                    self._save_cache(language)
        texts, indices = self._byLanguage[language]['texts'], self._byLanguage[language]['indices']
        return texts, indices

    def _load_cache(self, language):
        with open(f'{self.app_config["RitmomRoot"]}/cache/{language}.idx', 'rb') as f:
            self._byLanguage[language] = pickle.load(f)

    def _save_cache(self, language):
        with open(f'{self.app_config["RitmomRoot"]}/cache/{language}.idx', 'wb') as f:
            pickle.dump(self._byLanguage[language], f)
        with open(f'{self.app_config["RitmomRoot"]}/cache/{language}.ready', 'wb') as f:
            pass