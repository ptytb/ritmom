# coding: utf-8
import traceback

from comtypes.client import CreateObject
from multiprocessing import Queue, Process
from win32com.client import Dispatch
from comtypes.gen import SpeechLib

from datetime import datetime

from subprocess import Popen, DEVNULL, STDOUT

from operator import contains
from functools import partial

from os.path import abspath
from os import mkdir
from json import load
import csv
import re
import argparse

import nltk.corpus
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.text import ConcordanceIndex
from nltk.corpus import wordnet

import pickle
import dill

from os.path import exists


class PhraseSampler:
    """
    Provides definition, examples and excerpts.
    Excerpts are taken from corpuses listed by **phraseExamples** option.
    """
    def __init__(self, language):
        corpus_names = app_config['phraseExamples'][language]
        self.lemmatizer = WordNetLemmatizer()
        self.language = language

        if exists(f'cache/{language}.idx'):
            print('cache found, loading...', end='', flush=True)
            self._load_cache()
        else:
            self.texts = dict()
            self.indices = dict()
            for corpus_name in corpus_names:
                corpus = getattr(nltk.corpus, corpus_name)
                text = self.texts[corpus_name] = nltk.Text(corpus.words())
                self.indices[corpus_name] = ConcordanceIndex(text.tokens, key=lambda s: s.lower())
            print('saving cache...', end='', flush=True)
            self._save_cache()

    def _load_cache(self):
        with open(f'cache/{self.language}.t', 'rb') as f:
            self.texts = dill.load(f)
        with open(f'cache/{self.language}.idx', 'rb') as f:
            self.indices = dill.load(f)

    def _save_cache(self):
        with open(f'cache/{self.language}.t', 'wb') as f:
            dill.dump(self.texts, f)
        with open(f'cache/{self.language}.idx', 'wb') as f:
            dill.dump(self.indices, f)

    def get_excerpt(self, word):
        sentences = list()
        boundary_chars = ('.', ',', ':', '!', ';', '(', ')', '"', '、', '。', '\n')

        for corpus_name in self.indices:
            index = self.indices[corpus_name]
            text = self.texts[corpus_name]

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
                    sentences.append(app_config['phraseJoinChar'][self.language].join(sentence) + '.')

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

    def get_definitions_and_examples(self, word):
        """
        Tries to find in synsets which have format "word.pos.N". We only search for exactly the same word

        :param word: a word to be found in corpus
        :return: a fragment of text
        """
        language_nltk_naming = {
            "english": "eng",
            "japanese": "jpn",
        }

        definitions, examples = None, None
        synsets = wordnet.synsets(word, lang=language_nltk_naming[self.language])
        if synsets is not None:
            synsets = [synset for synset in synsets if synset.name().split('.')[0] == word]
            examples = [example for examples in [synset.examples() for synset in synsets] for example in examples]
            definitions = [s.definition() for s in synsets]
        return definitions, examples


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
    def write_silence(stream, sec):
        wf = stream.Format.GetWaveFormatEx()
        silence = (0, ) * int(sec * wf.SamplesPerSec * (wf.BitsPerSample // 8))
        stream.Write(silence)

    @staticmethod
    def load_wav(path):
        stream = CreateObject("SAPI.SpFileStream")
        stream.Open(path)
        return stream

    def __init__(self, config):
        self.sounds = sounds = dict()
        for k, v in config.items():
            if v.startswith('silence'):
                duration = float(v[v.find(' '):])
                stream = CreateObject("SAPI.SpMemoryStream")
                self.write_silence(stream, duration)
                sounds[k] = stream
            else:
                sounds[k] = self.load_wav(v)

    def __getitem__(self, key):
        return self.sounds[key]


class AudioBuilder:
    def __init__(self, *, languages, words_per_audio=10, sounds):
        def split_name_pair(name_pair):
            i = list(re.finditer(r'[A-Z]', language_pair))[1].span()[0]
            return name_pair[:i].lower(), name_pair[i:].lower()

        self.engine = CreateObject("SAPI.SpVoice")
        self.words_per_audio = words_per_audio
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
        self.streams = dict()

        self.samplers = dict()
        for language in app_config['phraseExamples']:
            print(f'Indexing phrase examples for {language}...', end='', flush=True)
            self.samplers[language] = PhraseSampler(language)
            print('done.')

    @staticmethod
    def _start_conversion_process(language_pair, fn):
        encode_queue.put((language_pair, fn))

    def _get_engine(self, language_pair, fn):
        print(f'Creating track {language_pair} #{fn}...')
        engine = CreateObject("SAPI.SpVoice")
        stream = CreateObject("SAPI.SpFileStream")
        if language_pair not in self.streams:
            self.streams[language_pair] = dict()
            self.streams[language_pair]['count'] = 0
        self.streams[language_pair]['engine'] = engine
        self.streams[language_pair]['stream'] = stream
        try:
            mkdir(f'audio/{language_pair}')
        except OSError:
            pass
        stream.Open(f'audio/{language_pair}/audio{fn:03}.wav', SpeechLib.SSFMCreateForWrite)
        engine.AudioOutputStream = stream
        return engine, stream

    def _search_excerpt(self, foreign_name, word):
        if foreign_name not in self.samplers or ' ' in word:
            return None
        example = self.samplers[foreign_name].get_excerpt(word)
        if example is None:
            # Try to find example for lemmatized form
            base_form = self.samplers[foreign_name].lemmatizer.lemmatize(word)
            if base_form != word:
                example = self.samplers[foreign_name].get_excerpt(word)
        return example

    def make_audio_tracks(self, source):
        lines = source.lines()

        for language_pair, word, trans in lines:
            if language_pair not in app_config['languages']:
                continue

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            if language_pair in self.streams:
                engine, stream = self.streams[language_pair]['engine'], self.streams[language_pair]['stream']
            else:
                engine, stream = self._get_engine(language_pair, 0)
            count = self.streams[language_pair]['count']

            if count % self.words_per_audio == 0 and count > 0:
                # Start a new audio track file
                engine.SpeakStream(self.sounds['end_of_part'])
                stream.Close()
                track_num = count // self.words_per_audio
                if track_num > 0:
                    self._start_conversion_process(language_pair, track_num - 1)  # Conversion and deletion in a separate process
                engine, stream = self._get_engine(language_pair, track_num)
                
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
                if foreign_name not in self.samplers:
                    continue

                definitions, examples = self.samplers[foreign_name].get_definitions_and_examples(word)

                if definitions is not None:
                    for definition in definitions:
                        engine.Volume = 50
                        engine.SpeakStream(self.sounds['definition'])
                        engine.SpeakStream(self.sounds['silence'])
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        engine.Speak(definition + '.')
                        engine.SpeakStream(self.sounds['silence_long'])

                if examples is not None:
                    for example in examples:
                        engine.Volume = 50
                        engine.SpeakStream(self.sounds['page_flipping'])
                        engine.SpeakStream(self.sounds['silence'])

                        engine.Rate = 0
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        engine.Speak(example)
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

            self.streams[language_pair]['count'] += 1

        # Close and convert last tracks
        for language_pair in self.streams:
            count = self.streams[language_pair]['count']
            if count % self.words_per_audio != 0:
                self.streams[language_pair]['stream'].Close()
                print(f"{language_pair}: total {count} words")
                track_num = count // self.words_per_audio
                self._start_conversion_process(language_pair, track_num)  # Conversion and deletion in a separate process


class EncoderWorker(Process):
    def __init__(self, queue):
        self.queue: Queue = queue
        super(EncoderWorker, self).__init__()

    def run(self):
        while True:
            language_pair, fn = self.queue.get()
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', help='List voice engines', action='store_true')
    args = parser.parse_args()

    if args.l:
        list_engines()
        exit(0)

    app_config = load(open('config.json'))
    audio_builder = AudioBuilder(languages=app_config['languages'],
                                 words_per_audio=app_config['words_per_audio'],
                                 sounds=app_config['sounds'])

    encode_queue = Queue()
    encode_worker = EncoderWorker(encode_queue)
    encode_worker.start()

    time_start = datetime.utcnow()
    audio_builder.make_audio_tracks(source=get_source(app_config['phrasebook']))
    print(f'time taken: {(datetime.utcnow() - time_start).total_seconds()} sec.')
