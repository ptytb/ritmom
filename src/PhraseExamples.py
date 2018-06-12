from collections import namedtuple
from itertools import chain, repeat, cycle

from nltk import WordNetLemmatizer
from nltk.corpus import wordnet
from word_forms.word_forms import get_word_forms

from src.Sequencer import TextChunk, as_chunks, JingleChunk
from src.Translator import Translator
from src.WordNetCache import WordNetCache
from src.utils.lists import flatten


class PhraseExamples:
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

        appendix = [
            JingleChunk(jingle='silence_long')
        ]

        def lemma_word(lemma_name):
            return lemma_name.split('.')[0]

        def lemma_name(lemma):
            return repr(lemma)[7:]

        all_lemmas = wordnet.lemmas(word, lang=language_nltk_naming[language])
        if len(all_lemmas) > 0:
            word_en = word if language == 'english' else lemma_word(lemma_name(all_lemmas[0]))
            lemmas = [l for l in all_lemmas if lemma_name(l).startswith(word_en)]  # skip 'Lemma('
            # lemmas = [l for l in all_lemmas if l.name() == word]
            synsets = [l.synset() for l in lemmas]

            jingles = [
                JingleChunk(jingle='definition', volume=50),
                JingleChunk(jingle='silence')
            ]
            definitions = [s.definition() for s in synsets]
            definitions = as_chunks(definitions, language=language, prepend=jingles, append=appendix)

            jingles = [
                JingleChunk(jingle='usage_example', volume=50),
                JingleChunk(jingle='silence')
            ]
            examples = [e for s in synsets for e in s.examples() if word in e]
            examples = as_chunks(examples, language=language, prepend=jingles, append=appendix)

            jingles = [
                JingleChunk(jingle='antonym', volume=50),
                JingleChunk(jingle='silence')
            ]
            antonyms = {a.name() for l in lemmas for a in l.antonyms()}
            antonyms = as_chunks(antonyms, language, prepend=jingles, append=appendix)

            jingles = [
                JingleChunk(jingle='synonym', volume=50),
                JingleChunk(jingle='silence')
            ]
            synonyms = {lemma_word(s.name()) for s in synsets} - {word}
            synonyms = as_chunks(synonyms, language, prepend=jingles, append=appendix)
        else:
            # definitions, examples, synonyms, antonyms = (list(),) * 4
            definitions, examples, synonyms, antonyms = [], [], [], []

        # synsets = wordnet.synsets(word, lang=language_nltk_naming[self.language])
        # if synsets is not None:
        #     synsets = [synset for synset in synsets if synset.name().split('.')[0] == word]
        #     examples = [example for examples in [synset.examples() for synset in synsets] for example in examples]
        #     definitions = [s.definition() for s in synsets]

        jingles = [
            JingleChunk(jingle='usage_example', volume=50),
            JingleChunk(jingle='silence')
        ]

        thesaurus_lang = language.capitalize()
        thesaurus_definition = self.translator.translate(word, f'{thesaurus_lang}{thesaurus_lang}')
        thesaurus_definitions = [thesaurus_definition] if thesaurus_definition else []
        thesaurus_definitions = as_chunks(thesaurus_definitions, language, prepend=jingles, append=appendix)

        examples_with_jingles = flatten([[jingles, exs, appendix]
                                         for exs in self.translator.get_examples(word, language)])

        examples = chain(examples, thesaurus_definitions, examples_with_jingles)

        return self.WordInfo(*map(list, [definitions, examples, synonyms, antonyms]))

    def search_excerpt(self, app_config, foreign_name, word):
        if ' ' in word or foreign_name not in app_config['phraseExamples']:
            return None
        example = self.get_excerpt(word, foreign_name)
        if example is None:
            # Try to find an example for lemmatized (stemmed) form
            base_forms = self.lemmatize(word)
            for base_form in base_forms:
                example = self.get_excerpt(base_form, foreign_name)
                if example:
                    break
        return [
            JingleChunk(jingle='excerpt'),
            JingleChunk(jingle='silence'),
            TextChunk(text=example, language=foreign_name),
            JingleChunk(jingle='silence_long')
        ] if example else None
