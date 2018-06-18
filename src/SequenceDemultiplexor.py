from datetime import datetime
from enum import IntEnum
from os import mkdir

from comtypes.client import CreateObject
from comtypes.gen import SpeechLib

from src.AudioJingles import AudioJingles
from src.Sequencer import AudioChunkMixin, Chunk, SpeechChunk, TextChunk, JingleChunk
from src.TextBuilder import TextBuilder


class SpeechStreamSeekPositionType(IntEnum):
    SSSPTRelativeToStart = 0
    SSSPTRelativeToCurrentPosition = 1
    SSSPTRelativeToEnd = 2


class SequenceDemultiplexor:
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