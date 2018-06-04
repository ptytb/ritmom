from os import mkdir

from comtypes.gen import SpeechLib
from operator import contains
from functools import partial
from enum import IntEnum
from comtypes.client import CreateObject
import re
from datetime import datetime

from src.AudioJingles import AudioJingles
from src.TextBuilder import TextBuilder
from src.PhraseExamples import PhraseExamples
from src.postprocessing.lang_jp_reverse import jp_reverse


class SpeechStreamSeekPositionType(IntEnum):
    SSSPTRelativeToStart = 0
    SSSPTRelativeToCurrentPosition = 1
    SSSPTRelativeToEnd = 2


class AudioBuilder:
    def __init__(self, *, app_config, encode_queue, only_wav):
        languages = app_config['languages']
        self.sounds = app_config['jingles']
        self.encode_queue = encode_queue
        self.app_config = app_config
        self.only_wav = only_wav

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

        self.sounds = AudioJingles(self.sounds)
        self.sampler = PhraseExamples(app_config)

        self.text_builder = TextBuilder(app_config)

    def _start_conversion_process(self, language_pair, fn):
        self.encode_queue.put((language_pair, fn))

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
        if ' ' in word or foreign_name not in self.app_config['phraseExamples']:
            return None
        example = self.sampler.get_excerpt(word, foreign_name)
        if example is None:
            # Try to find an example for lemmatized (stemmed) form
            base_forms = self.sampler.lemmatize(word)
            for base_form in base_forms:
                example = self.sampler.get_excerpt(base_form, foreign_name)
                if example:
                    break
        return example

    def make_audio_track(self, language_pair, lines, track_num):
        engine, stream = self._get_engine(language_pair, track_num)
        self.text_builder.open(language_pair, track_num)

        def speak(text):
            engine.Speak(text)
            if voice_num == 1:
                self.text_builder.speak(text)

        def speak_postprocess(text):
            if voice_num == 1:
                self.text_builder.speak_with_postprocess(text, language_pair)

        wf = stream.Format.GetWaveFormatEx()
        stream_position_divider = int(wf.SamplesPerSec * (wf.BitsPerSample // 8))

        def speak_jingle(jingle_name):
            if jingle_name == 'timestamp':
                stream_position_bytes = stream.Seek(0, SpeechStreamSeekPositionType.SSSPTRelativeToCurrentPosition)
                stream_position_seconds = stream_position_bytes // stream_position_divider
                t = datetime.utcfromtimestamp(stream_position_seconds)
                self.text_builder.speak(f'{t.strftime("%H:%M:%S")}\n')
                return
            engine.SpeakStream(self.sounds[jingle_name])
            if voice_num == 1:
                self.text_builder.speak_jingle(jingle_name)

        for word, trans in lines:
            if language_pair not in self.app_config['languages']:
                return

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            speak_jingle('timestamp')

            # Say a phrase with both male and female narrators
            for voice_num in range(1, 3):
                engine.Rate = -6
                engine.Volume = 100
                engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                speak(f'{word}.')

                speak_jingle('silence')

                engine.Rate = 0
                engine.Volume = 80
                engine.Voice = self.voices_com.Item(self.voices[language_pair]['native'])
                if trans:
                    speak(f'{trans}.')
                    speak_jingle('silence_long')

                speak_postprocess(word)

            word_info = self.sampler.get_definitions_and_examples(word, foreign_name)
            if word_info:
                for voice_num in range(1, 3):
                    for definition in word_info.definitions:
                        engine.Volume = 50
                        speak_jingle('definition')
                        speak_jingle('silence')
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        speak(definition + '.')
                        speak_jingle('silence_long')

                    for example in word_info.examples:
                        engine.Volume = 50
                        speak_jingle('usage_example')
                        speak_jingle('silence')
                        engine.Rate = 0
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        speak(example)
                        speak_jingle('silence_long')

                    for synonym in word_info.synonyms:
                        engine.Volume = 50
                        speak_jingle('synonym')
                        speak_jingle('silence')
                        engine.Rate = 0
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        if foreign_name == 'japanese':
                            synonym = jp_reverse(synonym)
                        speak(synonym)
                        speak_jingle('silence_long')

                    for antonym in word_info.antonyms:
                        engine.Volume = 50
                        speak_jingle('antonym')
                        speak_jingle('silence')
                        engine.Rate = 0
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        if foreign_name == 'japanese':
                            antonym = jp_reverse(antonym)
                        speak(antonym)
                        speak_jingle('silence_long')

                    excerpt = self._search_excerpt(foreign_name, word)
                    if excerpt is not None:
                        engine.Volume = 50
                        speak_jingle('excerpt')
                        speak_jingle('silence')

                        engine.Rate = 0
                        engine.Volume = 100
                        engine.Voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        speak(excerpt)
                        speak_jingle('silence_long')

                        speak_postprocess(excerpt)

            voice_num = 1
            speak_jingle('silence_long')
            speak_jingle('silence_long')

        stream.Close()
        if not self.only_wav:
            self._start_conversion_process(language_pair, track_num)

