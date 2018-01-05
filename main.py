from comtypes.client import CreateObject
from win32com.client import Dispatch
from comtypes.gen import SpeechLib

from datetime import datetime

from subprocess import Popen

from operator import contains
from functools import partial

from os.path import abspath


class ExcelSource():
    def __init__(self):
        xl = Dispatch("Excel.Application")
        wb = xl.Workbooks.Open(abspath(r'phrases\Phrasebook.xlsm'))
        ws = wb.Sheets('ForAudio')
        #xl.Visible = True
        r = xl.Range('C:D') # .Select()
        self.table = r.GetValue()
        wb.Close()
        xl.Quit()

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


class Sounds:
    @staticmethod
    def write_silence(stream, sec):
        wf = stream.Format.GetWaveFormatEx()
        silence = (0, ) * int(sec * wf.SamplesPerSec * (wf.BitsPerSample // 8))
        stream.Write(silence)

    def load_wav(self, path):
        stream = CreateObject("SAPI.SpFileStream")
        stream.Open(path)
        return stream

    def __init__(self, config):
        self.sounds = sounds = dict()
        for k, v in config.items():
            if v.startswith('gap'):
                duration = float(v[v.find(' '):])
                stream = CreateObject("SAPI.SpMemoryStream")
                self.write_silence(stream, 0.2)
                sounds[k] = stream
            else:
                sounds[k] = self.load_wav(v)

    def __getitem__(self, key):
        return self.sounds[key]
            

class Translator:
    def __init__(self, *, languages, words_per_audio=10, sounds):
        self.engine, self.stream = self.get_engine(0)
        self.words_per_audio = words_per_audio
        self.voices = dict()

        self.voices_com = voices = self.engine.GetVoices()
        for purpose in languages:
            for i in range(voices.Count):
                desc = voices.Item(i).GetDescription()
                if desc.find(languages[purpose]) != -1:
                    self.voices[purpose] = i

        has_voice = partial(contains, self.voices)
        assert all(map(has_voice, ['lang1', 'lang2', 'trans']))

        self.sounds = Sounds(sounds)

    def start_convert(self, file_index):
        fn = file_index
        cmd_str = [
            *rf'ffmpeg -i audio/audio{fn-1:03}.wav -codec:a libmp3lame -qscale:a 2 audio/audio{fn-1:03}.mp3 && del audio\audio{fn-1:03}.wav'.split(sep=' ')
        ]
        Popen(cmd_str, shell=True)

    def get_engine(self, fn):
        engine = CreateObject("SAPI.SpVoice")
        stream = CreateObject("SAPI.SpFileStream")
        stream.Open(f'audio/audio{fn:03}.wav', SpeechLib.SSFMCreateForWrite)
        engine.AudioOutputStream = stream

        if fn > 0:
            self.start_convert(fn)

        return engine, stream

    def translate(self, source):
        lines = source.lines()

        for i, (word, trans) in enumerate(lines):
            if i % self.words_per_audio == 0:
                self.engine.SpeakStream(self.sounds['end_of_part'])
                self.stream.Close()
                self.engine, self.stream = self.get_engine(i // self.words_per_audio)
                
            try:
                for i in range(1, 3):
                    self.engine.Rate = -6
                    self.engine.Volume = 100
                    self.engine.Voice = self.voices_com.Item(self.voices[f'lang{i}'])
                    self.engine.Speak(f'{word}.')
                    
                    self.engine.SpeakStream(self.sounds['gap'])

                    self.engine.Rate = 0
                    self.engine.Volume = 80
                    self.engine.Voice = self.voices_com.Item(self.voices['trans'])
                    self.engine.Speak(f'{trans}.')
                    
                    self.engine.SpeakStream(self.sounds['gap'])

                    self.engine.SpeakStream(self.sounds['gap_long'])

            except Exception as e:
                print(f'{word} = {trans}: {str(e)}')



translator = Translator(
    words_per_audio=100,
    languages={
        "lang1": 'Salli',
        "lang2": 'Brian',
        "trans": 'Milena'
        }, 
    sounds={
        'gap': 'gap 0.2',
        'gap_long': 'gap 0.5',
        'end_of_part': 'sounds/ding.wav'
    })


source = ExcelSource()
time_start = datetime.utcnow()
translator.translate(source)
print(f'time taken: {(datetime.utcnow() - time_start).total_seconds()} sec.')




##import io
##import wave
##import winsound


##
##buffer = io.BytesIO()
##memory_file = wave.open(buffer, 'wb')
##mf_samples = 2
##mf_rate = 22000
##memory_file.setnchannels(1)
##memory_file.setsampwidth(mf_samples)
##memory_file.setframerate(mf_rate)


##def pause(sec):
##    return (0, ) * int(sec * mf_rate * mf_samples)



##engine = CreateObject("SAPI.SpVoice")
##engine.Rate = -4
##engine.Volume = 100

##stream = CreateObject("SAPI.SpMemoryStream")
##engine.AudioOutputStream = stream



##prev_len = 0
##def say_buffer(text, voice):
##    global prev_len
##    engine.Voice = voices.Item(voice)
##    engine.Speak(f'{text}.')
##
##    d = stream.GetData()
##    l = len(d)
##    data = d[prev_len:l]
##    print(prev_len, l)
##    prev_len = l
##    
##    return bytes(data)


##        memory_file.writeframes(say_buffer(word, 1))
##        memory_file.writeframes(pause(1.0))
##        memory_file.writeframes(say_buffer(trans, 3))
##        memory_file.writeframes(pause(2.0))

        #winsound.PlaySound(buffer.getbuffer(), winsound.SND_MEMORY)
        

##memory_file_buffer = buffer.getbuffer()
##
##with open('audio.wav', 'wb') as out:
##    out.write(memory_file_buffer.tobytes())


#wb.Close()
#xl.Quit()

##for book in xl.Workbooks: if book.Name=='simplenew4.xls': book.Close()
