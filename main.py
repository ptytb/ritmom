from comtypes.client import CreateObject
from win32com.client import Dispatch
from comtypes.gen import SpeechLib

from datetime import datetime

from subprocess import Popen

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
    def __init__(self, language):
        corpus_names = app_config['phraseExamples'][language]

        if exists(f'cache/{language}.idx'):
            print('\ncache found, loading...', end='', flush=True)
            with open(f'cache/{language}.t', 'rb') as f:
                self.texts = dill.load(f)
            with open(f'cache/{language}.idx', 'rb') as f:
                self.indices = dill.load(f)
        else:
            self.texts = dict()
            self.indices = dict()
            for corpus_name in corpus_names:
                corpus = getattr(nltk.corpus, corpus_name)
                text = self.texts[corpus_name] = nltk.Text(corpus.words())
                self.indices[corpus_name] = ConcordanceIndex(text.tokens, key=lambda s: s.lower())
            with open(f'cache/{language}.t', 'wb') as f:
                dill.dump(self.texts, f, )
            with open(f'cache/{language}.idx', 'wb') as f:
                dill.dump(self.indices, f, )

        self.lemmatizer = WordNetLemmatizer()
        self.language = language

    def get_sample_phrase(self, word):
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
                if len(sentence) > 3:
                    sentences.append(app_config['phraseJoinChar'][self.language].join(sentence) + '.')

        shortest_sentence = list(sorted(sentences, key=len))[0] if len(sentences) > 0 else None
        return shortest_sentence

    def get_definitions(self, word):
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
            word, trans = self.table[i]
            
            if word is None:
                gap += 1
                if gap == 15:
                    return
            else:
                gap = 0
                yield word, trans
                
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


class Translator:
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

        print('Indexing phrase examples...', end='', flush=True)
        self.samplers = dict()
        for language in app_config['phraseExamples']:
            self.samplers[language] = PhraseSampler(language)
        print('done.')

    @staticmethod
    def start_convert(language_pair, fn):
        cmd_str = [
            *rf'ffmpeg -y -i audio/{language_pair}/audio{fn:03}.wav -codec:a libmp3lame -qscale:a 2 audio/{language_pair}/audio{fn:03}.mp3 && del audio\{language_pair}\audio{fn:03}.wav'.split(sep=' ')
        ]
        Popen(cmd_str, shell=True)

    def get_engine(self, language_pair, fn):
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

    def get_sample_phrase(self, foreign_name, word):
        if foreign_name not in self.samplers:
            return None
        example = self.samplers[foreign_name].get_sample_phrase(word)
        if example is None:
            # Try to find example for lemmatized form
            base_form = self.samplers[foreign_name].lemmatizer.lemmatize(word)
            if base_form != word:
                example = self.samplers[foreign_name].get_sample_phrase(word)
        return example

    def translate(self, source):
        lines = source.lines()

        for language_pair, word, trans in lines:
            if language_pair not in app_config['languages']:
                continue

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            if language_pair in self.streams:
                engine, stream = self.streams[language_pair]['engine'], self.streams[language_pair]['stream']
            else:
                engine, stream = self.get_engine(language_pair, 0)
            count = self.streams[language_pair]['count']

            if count % self.words_per_audio == 0 and count > 0:
                engine.SpeakStream(self.sounds['end_of_part'])
                stream.Close()
                track_num = count // self.words_per_audio
                if track_num > 0:
                    self.start_convert(language_pair, track_num - 1)  # Conversion and deletion in a separate process
                engine, stream = self.get_engine(language_pair, track_num)
                
            try:
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

                    definitions, examples = self.samplers[foreign_name].get_definitions(word)

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
                            engine.SpeakStream(self.sounds['excerpt'])
                            engine.SpeakStream(self.sounds['silence'])

                            engine.Rate = 0
                            engine.Volume = 100
                            engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                            engine.Speak(example)
                            engine.SpeakStream(self.sounds['silence_long'])

                    if ' ' not in word:
                        example = self.get_sample_phrase(foreign_name, word)
                        if example is not None:
                            engine.Volume = 50
                            engine.SpeakStream(self.sounds['excerpt'])
                            engine.SpeakStream(self.sounds['silence'])

                            engine.Rate = 0
                            engine.Volume = 100
                            engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                            engine.Speak(example)
                            engine.SpeakStream(self.sounds['silence_long'])
            except Exception as e:
                print(f'{word} = {trans}: {str(e)}')
            else:
                self.streams[language_pair]['count'] += 1

        # Close and convert last tracks
        for language_pair in self.streams:
            count = self.streams[language_pair]['count']
            if count % self.words_per_audio != 0:
                self.streams[language_pair]['stream'].Close()
                print(f"{language_pair}: total {count} words")
                track_num = count // self.words_per_audio
                self.start_convert(language_pair, track_num)  # Conversion and deletion in a separate process


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
    translator = Translator(languages=app_config['languages'],
                            words_per_audio=app_config['words_per_audio'],
                            sounds=app_config['sounds'])
    time_start = datetime.utcnow()
    translator.translate(source=get_source(app_config['phrasebook']))
    print(f'time taken: {(datetime.utcnow() - time_start).total_seconds()} sec.')
