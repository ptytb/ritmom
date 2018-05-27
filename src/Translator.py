from src.translate.Dictionary import Dictionary
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

        self.dictionaries = dict()
        self.all_dictionaries = list()
        self._load_dictionaries(dict_descriptors)

    def _load_dictionaries(self, dict_descriptors):
        for d in dict_descriptors:
            dictionary = Dictionary.load(d['file'], d['type'], d['encoding'])
            language_pair = d['pair']

            if language_pair not in self.dictionaries:
                self.dictionaries[language_pair] = list()

            self.dictionaries[language_pair].append(dictionary)
            self.all_dictionaries.append(dictionary)

    def translate(self, phrase, language_pair=None):
        if language_pair:
            dictionaries = self.dictionaries[language_pair]
        else:
            dictionaries = self.all_dictionaries

        summary = None

        for d in dictionaries:
            trans = d.translate_word(phrase)
            if trans:
                if not summary:
                    summary = trans
                else:
                    summary += ';' + trans

        return summary
