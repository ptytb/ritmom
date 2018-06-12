from copy import deepcopy
from os import mkdir

from comtypes.gen import SpeechLib
from operator import contains
from functools import partial
from enum import IntEnum
from comtypes.client import CreateObject
from datetime import datetime

from src.AudioJingles import AudioJingles
from src.Sequencer import Sequencer, TextChunk, Chunk, JingleChunk, SpeechChunk, AudioChunkMixin
from src.TextBuilder import TextBuilder
from src.PhraseExamples import PhraseExamples

from src.utils.config import split_name_pair
from src.utils.term_progress import print_progressbar


class SpeechStreamSeekPositionType(IntEnum):
    SSSPTRelativeToStart = 0
    SSSPTRelativeToCurrentPosition = 1
    SSSPTRelativeToEnd = 2


class ChunkDemultiplexor:
    def __init__(self, app_config, sequencer, encode_queue, only_wav):
        self.text_builder = TextBuilder(app_config)
        self.sequencer = sequencer
        self.sounds = AudioJingles(app_config['jingles'])
        self.text_jingles = app_config['text_jingles']
        self.only_wav = only_wav
        self.encode_queue = encode_queue

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

    def start_section(self, language_pair, track_num):
        self.language_pair = language_pair
        self.track_num = track_num
        self.engine, self.stream = self._get_engine(language_pair, track_num)
        self.text_builder.open(language_pair, track_num)

    def stop_section(self):
        self.stream.Close()
        if not self.only_wav:
            self._start_conversion_process(self.language_pair, self.track_num)

    def get_time(self):
        wf = self.stream.Format.GetWaveFormatEx()
        stream_position_divider = int(wf.SamplesPerSec * (wf.BitsPerSample // 8))
        stream_position_bytes = self.stream.Seek(0, SpeechStreamSeekPositionType.SSSPTRelativeToCurrentPosition)
        stream_position_seconds = stream_position_bytes // stream_position_divider
        return stream_position_seconds

    def speak_jingle(self, chunk):
        jingle_name = chunk.jingle
        if jingle_name == 'timestamp' and chunk.printable:
            t = datetime.utcfromtimestamp(self.get_time())
            self.text_builder.speak(f'{t.strftime("%H:%M:%S")}\n')
            return
        if chunk.audible:
            if isinstance(chunk, AudioChunkMixin):
                self.engine.Volume = chunk.volume
                self.engine.Rate = chunk.rate
            self.engine.SpeakStream(self.sounds[jingle_name])
        if chunk.printable:
            self.text_builder.speak(self.text_jingles[jingle_name])

    def speak_audio(self, chunk: Chunk):
        if isinstance(chunk, SpeechChunk):
            self.engine.Rate = chunk.rate
            self.engine.Volume = chunk.volume
            self.engine.Voice = chunk.voice
        self.engine.Speak(chunk.text)

    def feed(self, chunk: Chunk):
        if isinstance(chunk, TextChunk):
            if chunk.audible:
                self.speak_audio(chunk)
            if chunk.printable:
                self.text_builder.speak(chunk.text)
        elif isinstance(chunk, JingleChunk):
            self.speak_jingle(chunk)


class AudioBuilder:
    def __init__(self, *, app_config, encode_queue, only_wav):
        languages = app_config['languages']
        self.app_config = app_config

        self.info_engine = CreateObject("SAPI.SpVoice")
        self.voices = dict()

        self.voices_com = voices = self.info_engine.GetVoices()
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

        self.phrase_examples = PhraseExamples(app_config)
        self.sequencer = Sequencer()
        self.chunk_demultiplexor = ChunkDemultiplexor(app_config, self.sequencer, encode_queue, only_wav)

    def make_audio_track(self, language_pair, lines, track_num):
        self.chunk_demultiplexor.start_section(language_pair, track_num)

        for word, trans in lines:
            if language_pair not in self.app_config['languages']:
                return

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            # Say a phrase with both male and female narrators
            for voice_num in range(1, 3):
                first_pass = voice_num == 1

                if first_pass:
                    self.sequencer.append(JingleChunk(jingle='timestamp'))

                voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                self.sequencer.append(SpeechChunk(text=word, language=foreign_name, final=not first_pass,
                                                  rate=-6, volume=100, voice=voice, printable=first_pass))
                self.sequencer.append(JingleChunk(jingle='silence_long', printable=first_pass))

                if trans:
                    trans = '; '.join(sorted(set(map(str.strip, trans.split(';')))))
                    voice = self.voices_com.Item(self.voices[language_pair]['native'])
                    self.sequencer.append(SpeechChunk(text=trans, language=native_name, final=True,
                                                      rate=0, volume=60, voice=voice, printable=first_pass))
                    self.sequencer.append(JingleChunk(jingle='silence', printable=first_pass))

                self.sequencer.append(JingleChunk(jingle='silence_long', printable=first_pass))

            word_info = self.phrase_examples.get_definitions_and_examples(word, foreign_name)
            if word_info:
                for voice_num in range(1, 3):
                    first_pass = voice_num == 1

                    for definition in word_info.definitions:
                        voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        if not isinstance(definition, JingleChunk):
                            definition = definition.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            definition.final = not first_pass
                        definition.printable = first_pass
                        self.sequencer.append(definition)

                    for example in word_info.examples:
                        if not isinstance(example, JingleChunk):
                            if example.language == foreign_name:
                                voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                                volume = 100
                            else:
                                voice = self.voices_com.Item(self.voices[language_pair]['native'])
                                volume = 50
                            example = example.promote(SpeechChunk, rate=0, volume=volume, voice=voice, final=True)
                            example.final = not first_pass
                        example.printable = first_pass
                        self.sequencer.append(example)

                    for synonym in word_info.synonyms:
                        voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        if not isinstance(synonym, JingleChunk):
                            synonym = synonym.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            synonym.final = not first_pass
                        synonym.printable = first_pass
                        self.sequencer.append(synonym)

                    for antonym in word_info.antonyms:
                        voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                        if not isinstance(antonym, JingleChunk):
                            antonym = antonym.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            antonym.final = not first_pass
                        antonym.printable = first_pass
                        self.sequencer.append(antonym)

                    excerpts = self.phrase_examples.search_excerpt(self.app_config, foreign_name, word)
                    if excerpts is not None:
                        for excerpt in excerpts:
                            if not isinstance(excerpt, JingleChunk):
                                voice = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                                excerpt = excerpt.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                                excerpt.final = not first_pass
                            excerpt.printable = first_pass
                            self.sequencer.append(excerpt)

            self.sequencer.append(JingleChunk(jingle='silence_long'))
            self.sequencer.append(JingleChunk(jingle='silence_long', printable=False))

        self.sequencer.append(JingleChunk(jingle='end_of_part', volume=20))

        while len(self.sequencer):
            self.chunk_demultiplexor.feed(self.sequencer.pop())

        self.chunk_demultiplexor.stop_section()
