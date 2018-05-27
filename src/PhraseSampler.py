from collections import namedtuple
from nltk import WordNetLemmatizer
from nltk.corpus import wordnet
from word_forms.word_forms import get_word_forms

from src.Translator import Translator
from src.WordNetCache import WordNetCache


class PhraseSampler:
    """
    Provides definition, examples and excerpts.
    Excerpts are taken from corpuses listed by **phraseExamples** option.
    """

    WordInfo = namedtuple('WordInfo', ['definitions', 'examples', 'synonyms', 'antonyms'])

    def __init__(self, app_config):
        self.app_config = app_config
        self.lemmatizers = [WordNetLemmatizer()]
        self.word_net_cache = WordNetCache(app_config)
        self.translator = Translator(app_config['dictionaries'])

    def lemmatize(self, word):
        for lemmatizer in self.lemmatizers:
            base_form = lemmatizer.lemmatize(word)
            if word != base_form and base_form is not None:
                return {base_form}
        word_forms = get_word_forms(word)
        all_forms = set()
        for base_forms_pos in word_forms:
            for base_form in word_forms[base_forms_pos]:
                if base_form != word:
                    all_forms.add(base_form)
        return all_forms

    def get_excerpt(self, word, language):
        sentences = list()
        boundary_chars = ('?', '.', ',', ':', '!', ';', '(', ')', '"', '、', '。', '\n')
        texts, indices = self.word_net_cache.get_cache(language)

        for corpus_name in indices:
            index = indices[corpus_name]
            text = texts[corpus_name]

            for offset in index.offsets(word):
                sentence_start = offset
                boundary_limit = 8
                while text[sentence_start] not in boundary_chars and sentence_start > 0 and boundary_limit > 0:
                    sentence_start -= 1
                    boundary_limit -= 1

                sentence_end = offset
                boundary_limit = 8
                while text[sentence_end] not in boundary_chars and sentence_end < len(text) and boundary_limit > 0:
                    sentence_end += 1
                    boundary_limit -= 1

                sentence = text[sentence_start + 1:sentence_end]
                if len(sentence) > 1:
                    sentences.append(self.app_config['phraseJoinChar'][language].join(sentence) + '.')

        shortest_sentence = sorted(sentences, key=len, reverse=True)[0] if len(sentences) > 0 else None
        return shortest_sentence

    def get_definitions_and_examples(self, word, language):
        """
        Tries to find in synsets which have format "word.pos.N". We only search for exactly the same word

        :param word: a word to be found in corpus
        :return: a fragment of text
        """
        language_nltk_naming = {
            "english": "eng",
            "japanese": "jpn",
        }

        def lemma_word(lemma_name):
            return lemma_name.split('.')[0]

        def lemma_name(lemma):
            return repr(lemma)[7:]

        all_lemmas = wordnet.lemmas(word, lang=language_nltk_naming[language])
        if len(all_lemmas) == 0:
            return None
        word_en = word if language == 'english' else lemma_word(lemma_name(all_lemmas[0]))
        lemmas = [l for l in all_lemmas if lemma_name(l).startswith(word_en)]  # skip 'Lemma('
        # lemmas = [l for l in all_lemmas if l.name() == word]
        synsets = [l.synset() for l in lemmas]
        definitions = [s.definition() for s in synsets]
        examples = [e for s in synsets for e in s.examples() if word in e]
        antonyms = list({a.name() for l in lemmas for a in l.antonyms()})
        synonyms = list({lemma_word(s.name()) for s in synsets} - {word})

        # synsets = wordnet.synsets(word, lang=language_nltk_naming[self.language])
        # if synsets is not None:
        #     synsets = [synset for synset in synsets if synset.name().split('.')[0] == word]
        #     examples = [example for examples in [synset.examples() for synset in synsets] for example in examples]
        #     definitions = [s.definition() for s in synsets]

        thesaurus_lang = language.capitalize()
        thesaurus_definition = self.translator.translate(word, f'{thesaurus_lang}{thesaurus_lang}')
        if thesaurus_definition:
            definitions.append(thesaurus_definition)

        return self.WordInfo(definitions, examples, synonyms, antonyms)
