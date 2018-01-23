# coding: utf-8

import pickle
# import dill

from multiprocessing.pool import Pool
from multiprocessing import Manager
from multiprocessing import Process
from subprocess import Popen, DEVNULL, STDOUT

from traceback import print_exc

from comtypes.client import CreateObject
from win32com.client import Dispatch
from comtypes.gen import SpeechLib

from datetime import datetime

from operator import contains
from functools import partial

from os.path import abspath
from os import mkdir, cpu_count
from json import load
import csv
import re
import argparse

import nltk.corpus
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.text import ConcordanceIndex
from nltk.corpus import wordnet

from os.path import exists

from collections import namedtuple

# dill.detect.trace(True)


# class SharedLockable(type):
#     @classmethod
#     def set_lock(cls, lock):
#         cls._lock = lock
#
#     @classmethod
#     def get_lock(cls):
#         return cls._lock
#
#     def __new__(cls, name, bases, attrs):
#         if __name__ == '__main__':
#             cls.set_lock(Lock())
#         newattrs = {"get_lock": lambda: cls._lock}
#         attrs.update(newattrs)
#         klass = super().__new__(cls, name, bases, attrs)
#         return klass


class WordNetCache:
    _lock = None

    @classmethod
    def get_lock(cls):
        return cls._lock

    def __init__(self):
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
                    corpus_names = app_config['phraseExamples'][language]
                    for corpus_name in corpus_names:
                        corpus = getattr(nltk.corpus, corpus_name)
                        text = self._byLanguage[language]['texts'][corpus_name] = nltk.Text(corpus.words())
                        self._byLanguage[language]['indices'][corpus_name] = ConcordanceIndex(text.tokens,
                                                                                              key=self.key_func)
                    self._save_cache(language)
        texts, indices = self._byLanguage[language]['texts'], self._byLanguage[language]['indices']
        return texts, indices

    def _load_cache(self, language):
        with open(f'cache/{language}.idx', 'rb') as f:
            self._byLanguage[language] = pickle.load(f)

    def _save_cache(self, language):
        with open(f'cache/{language}.idx', 'wb') as f:
            pickle.dump(self._byLanguage[language], f)
        with open(f'cache/{language}.ready', 'wb') as f:
            pass


class PhraseSampler:
    """
    Provides definition, examples and excerpts.
    Excerpts are taken from corpuses listed by **phraseExamples** option.
    """

    WordInfo = namedtuple('WordInfo', ['definitions', 'examples', 'synonyms', 'antonyms'])

    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.word_net_cache = WordNetCache()

    def get_excerpt(self, word, language):
        sentences = list()
        boundary_chars = ('.', ',', ':', '!', ';', '(', ')', '"', '、', '。', '\n')
        texts, indices = self.word_net_cache.get_cache(language)

        for corpus_name in indices:
            index = indices[corpus_name]
            text = texts[corpus_name]

            for offset in index.offsets(word):
                sentence_start = offset
                boundary_limit = 5
                while text[sentence_start] not in boundary_chars and sentence_start > 0 and boundary_limit > 0:
                    sentence_start -= 1
                    boundary_limit -= 1

                sentence_end = offset
                boundary_limit = 5
                while text[sentence_end] not in boundary_chars and sentence_end < len(text) and boundary_limit > 0:
                    sentence_end += 1
                    boundary_limit -= 1

                sentence = text[sentence_start + 1:sentence_end]
                if 3 < len(sentence) < 7:
                    sentences.append(app_config['phraseJoinChar'][language].join(sentence) + '.')

        shortest_sentence = sorted(sentences, key=len, reverse=True)[0] if len(sentences) > 0 else None
        return shortest_sentence

    def get_definitions_jpn_experiments(self):
        # synsets = wordnet.synsets(word, lang=language_nltk_naming[self.language])
        # jaconv.hira2kata(u'ともえまみ', STDOUT)

        # analyzer = ASA(r'd:\prog\ASA\ASA20170503.jar')
        # analyzer.parse('彼は村長だ')

        # os.environ['CJKDATA'] = r'D:\Src\Lang\Nihon\cjkdata\cjkdata'
        # from cjktools.resources.radkdict import RadkDict
        # print(', '.join(RadkDict())[u'明'])
        ...

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

        all_lemmas = wordnet.lemmas(word)
        lemmas = [l for l in all_lemmas if repr(l)[7:].startswith(word)]
        definitions = [l.synset().definition() for l in lemmas]
        examples = [e for l in lemmas for e in l.synset().examples() if word in e]
        antonyms = list({a.name() for l in lemmas for a in l.antonyms()})
        synsets = [l.synset() for l in all_lemmas]
        synonyms = list({lemma_word(s.name()) for s in synsets} - {word})

        # synsets = wordnet.synsets(word, lang=language_nltk_naming[self.language])
        # if synsets is not None:
        #     synsets = [synset for synset in synsets if synset.name().split('.')[0] == word]
        #     examples = [example for examples in [synset.examples() for synset in synsets] for example in examples]
        #     definitions = [s.definition() for s in synsets]

        return self.WordInfo(definitions, examples, synonyms, antonyms)


def unroll_multi_line_cell(gen_lines_func):
    """
    Decorator for tidying the output of the dictionary sources

    :param gen_lines_func: a function returning rows (possibly with multiline cells) from source
    :return: a function returning tuple: LanguagePair, foreign word, translation to native
    """
    def lines_func(*args):
        lines = gen_lines_func(*args)
        while True:
            line = next(lines)
            language_pair = f'{line[0]}{line[1]}' if len(line) > 2 else app_config['default']
            if len(line) == 2:
                foreign, native = line
            else:
                foreign, native = line[2:4]
            if '\n' in foreign:
                pairs = zip(foreign.split('\n'), native.split('\n'))
                for pair in pairs:
                    yield (language_pair, *pair)
            else:
                yield language_pair, foreign, native

    return lines_func


class ExcelSource:
    def __init__(self, phrasebook):
        xl = Dispatch("Excel.Application")
        wb = xl.Workbooks.Open(abspath(phrasebook))
        # ws = wb.Sheets('ForAudio')
        xl.Visible = True
        r = xl.Range('C:D')  # col C: foreign, col D: native
        self.table = r.GetValue()
        wb.Close()
        xl.Quit()

    @unroll_multi_line_cell
    def lines(self, start=0, end=None):
        """Generator. Scans Excel columns until two empty lines reached."""
        i = start
        gap = 0
        while not end or i > end:
            word = self.table[i][0]
            
            if word is None:
                gap += 1
                if gap == 15:
                    return
            else:
                gap = 0
                yield self.table[i]
                
            i += 1


class CsvSource:
    def __init__(self, source):
        self.source = abspath(source)

    @unroll_multi_line_cell
    def lines(self):
        with open(self.source, newline='', errors='replace', encoding='utf-8') as f:
            csvreader = csv.reader(f)
            for row in csvreader:
                yield row


class Sounds:
    @staticmethod
    def _write_silence(stream, sec):
        wf = stream.Format.GetWaveFormatEx()
        silence = (0, ) * int(sec * wf.SamplesPerSec * (wf.BitsPerSample // 8))
        stream.Write(silence)

    @staticmethod
    def load_wav(path):
        stream = CreateObject("SAPI.SpFileStream")
        stream.Open(path)
        return stream

    def __init__(self, config):
        self._sounds = sounds = dict()
        for k, v in config.items():
            if v.startswith('silence'):
                duration = float(v[v.find(' '):])
                stream = CreateObject("SAPI.SpMemoryStream")
                self._write_silence(stream, duration)
                sounds[k] = stream
            else:
                sounds[k] = self.load_wav(v)

    def __getitem__(self, key):
        return self._sounds[key]


class AudioBuilder:
    def __init__(self, *, languages, sounds):
        def split_name_pair(name_pair):
            i = list(re.finditer(r'[A-Z]', language_pair))[1].span()[0]
            return name_pair[:i].lower(), name_pair[i:].lower()

        self.engine = CreateObject("SAPI.SpVoice")
        self.voices = dict()

        self.voices_com = voices = self.engine.GetVoices()
        for language_pair in languages:
            self.voices[language_pair] = dict()

            foreign_name, native_name = split_name_pair(language_pair)
            self.voices[language_pair]['native_name'] = native_name
            self.voices[language_pair]['foreign_name'] = foreign_name

            for purpose in languages[language_pair]:
                for i in range(voices.Count):
                    desc = voices.Item(i).GetDescription()
                    if desc.find(languages[language_pair][purpose]) != -1:
                        self.voices[language_pair][purpose] = i

            has_voice = partial(contains, self.voices[language_pair])
            assert all(map(has_voice, ['foreign1', 'foreign2', 'native']))

        self.sounds = Sounds(sounds)
        self.sampler = PhraseSampler()

    @staticmethod
    def _start_conversion_process(language_pair, fn):
        encode_queue.put((language_pair, fn))

    @staticmethod
    def _get_engine(language_pair, fn):
        print(f'Creating track {language_pair} #{fn}...')
        engine = CreateObject("SAPI.SpVoice")
        stream = CreateObject("SAPI.SpFileStream")
        try:
            mkdir(f'audio/{language_pair}')
        except OSError:
            pass
        stream.Open(f'audio/{language_pair}/audio{fn:03}.wav', SpeechLib.SSFMCreateForWrite)
        engine.AudioOutputStream = stream
        return engine, stream

    def _search_excerpt(self, foreign_name, word):
        if ' ' in word:
            return None
        example = self.sampler.get_excerpt(word, foreign_name)
        if example is None:
            # Try to find example for lemmatized form
            base_form = self.sampler.lemmatizer.lemmatize(word)
            if base_form != word:
                example = self.sampler.get_excerpt(word, foreign_name)
        return example

    def make_audio_track(self, language_pair, lines, track_num):
        engine, stream = self._get_engine(language_pair, track_num)

        for word, trans in lines:
            if language_pair not in app_config['languages']:
                return

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            # Say a phrase with both male and female narrators
            for voice_num in range(1, 3):
                engine.Rate = -6
                engine.Volume = 100
                engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                engine.Speak(f'{word}.')

                engine.SpeakStream(self.sounds['silence'])

                engine.Rate = 0
                engine.Volume = 80
                engine.Voice = self.voices_com.Item(self.voices[language_pair]['native'])
                engine.Speak(f'{trans}.')

                engine.SpeakStream(self.sounds['silence_long'])

            for voice_num in range(1, 3):
                # if foreign_name not in self.sampler:
                #     continue

                word_info = self.sampler.get_definitions_and_examples(word, foreign_name)

                for definition in word_info.definitions:
                    engine.Volume = 50
                    engine.SpeakStream(self.sounds['definition'])
                    engine.SpeakStream(self.sounds['silence'])
                    engine.Volume = 100
                    engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    engine.Speak(definition + '.')
                    engine.SpeakStream(self.sounds['silence_long'])

                for example in word_info.examples:
                    engine.Volume = 50
                    engine.SpeakStream(self.sounds['page_flipping'])
                    engine.SpeakStream(self.sounds['silence'])
                    engine.Rate = 0
                    engine.Volume = 100
                    engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    engine.Speak(example)
                    engine.SpeakStream(self.sounds['silence_long'])

                for synonym in word_info.synonyms:
                    engine.Volume = 50
                    engine.SpeakStream(self.sounds['synonym'])
                    engine.SpeakStream(self.sounds['silence'])
                    engine.Rate = 0
                    engine.Volume = 100
                    engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    engine.Speak(synonym)
                    engine.SpeakStream(self.sounds['silence_long'])

                for antonym in word_info.antonyms:
                    engine.Volume = 50
                    engine.SpeakStream(self.sounds['antonym'])
                    engine.SpeakStream(self.sounds['silence'])
                    engine.Rate = 0
                    engine.Volume = 100
                    engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    engine.Speak(antonym)
                    engine.SpeakStream(self.sounds['silence_long'])

                excerpt = self._search_excerpt(foreign_name, word)
                if excerpt is not None:
                    engine.Volume = 50
                    engine.SpeakStream(self.sounds['excerpt'])
                    engine.SpeakStream(self.sounds['silence'])

                    engine.Rate = 0
                    engine.Volume = 100
                    engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    engine.Speak(excerpt)
                    engine.SpeakStream(self.sounds['silence_long'])

        stream.Close()
        self._start_conversion_process(language_pair, track_num)


class EncoderWorker(Process):
    def __init__(self, queue):
        self.queue = queue
        super(EncoderWorker, self).__init__()

    def run(self):
        while True:
            value = self.queue.get()
            if value is None:
                break
            language_pair, fn = value
            target_track_name = rf'audio/{language_pair}/audio{fn:03}.mp3'
            print(f'Encoding {target_track_name}')
            cmd_str = [
                rf'ffmpeg', '-y', '-i',
                rf'audio/{language_pair}/audio{fn:03}.wav',
                rf'-codec:a', 'libmp3lame', '-qscale:a', '2',
                target_track_name,
                rf'&&',
                rf'del',
                rf'audio\{language_pair}\audio{fn:03}.wav'
            ]
            pipe = Popen(cmd_str, shell=True, stdout=DEVNULL, stderr=STDOUT)
            out, err = pipe.communicate()
            pipe.wait()
            if not exists(target_track_name):
                print(f'Failed to create {target_track_name}')
                print(f'{str(err)}')


def get_source(file_path):
    if re.search(r'\.xls(m)?$', file_path):
        return ExcelSource(file_path)
    elif re.search(r'\.csv$', file_path):
        return CsvSource(file_path)
    else:
        raise Exception(f'Type of source "{file_path}" is undetermined')


def list_engines():
    engine = CreateObject("SAPI.SpVoice")
    voices = engine.GetVoices()
    for i in range(voices.Count):
        desc = voices.Item(i).GetDescription()
        print(f'#{i} {desc}')


def init_audio_builder(_encode_queue, _app_config, _lock):
    """
    This will initialize a worker process
    :param _encode_queue:
    :param _app_config:
    :param _lock:
    :return:
    """
    global audio_builder
    global app_config
    global encode_queue
    app_config = _app_config
    encode_queue = _encode_queue
    WordNetCache._lock = _lock
    audio_builder = AudioBuilder(languages=app_config['languages'],
                                 sounds=app_config['sounds'])


def make_audio_track(language_pair, items, part_number):
    """
    This will be executed as payload from a worker process
    :param language_pair:
    :param items:
    :param part_number:
    :return:
    """
    global audio_builder
    try:
        audio_builder.make_audio_track(language_pair, items, part_number)
    except Exception as e:
        print(str(e))
        print_exc()


if __name__ == '__main__':
    app_config = load(open('config.json'))

    # WordNetCache._lock = Lock()
    # c = WordNetCache()
    # c.get_cache('english')
    # exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', help='List voice engines', action='store_true')
    args = parser.parse_args()

    if args.l:
        list_engines()
        exit(0)

    with Manager() as multiprocessing_manager:
        _lock = multiprocessing_manager.Lock()

        encode_queue = multiprocessing_manager.Queue()
        encode_worker = EncoderWorker(encode_queue)
        encode_worker.start()

        time_start = datetime.utcnow()

        phrasebook = get_source(app_config['phrasebook'])
        with Pool(processes=cpu_count() - 2,
                  initializer=init_audio_builder,
                  initargs=(encode_queue, app_config, _lock)) as pool:
            def process_chunk():
                pool.apply_async(make_audio_track, (language_pair,
                                                    builder_queue.pop(language_pair),
                                                    builder_parts[language_pair]))
                builder_queue[language_pair] = list()
                builder_parts[language_pair] += 1
            builder_queue = dict()
            builder_parts = dict()
            for language_pair, word, trans in phrasebook.lines():
                if language_pair not in app_config['languages']:
                    continue
                if language_pair not in builder_queue:
                    builder_queue[language_pair] = list()
                    builder_parts[language_pair] = 0
                builder_queue[language_pair].append((word, trans))
                if len(builder_queue[language_pair]) > app_config['words_per_audio']:
                    process_chunk()
            for language_pair in builder_queue:
                process_chunk()

            pool.close()
            pool.join()

        encode_queue.put(None)
        encode_worker.join()
        encode_queue.close()
        encode_queue.join_thread()

    print(f'time taken: {(datetime.utcnow() - time_start).total_seconds()} sec.')
