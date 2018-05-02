from genericpath import exists
from multiprocessing import Process
from subprocess import Popen, DEVNULL, STDOUT


class AudioEncoderWorker(Process):
    """
    Converts .wav files being put into the queue, to .mp3 with ffmpeg.exe
    """

    def __init__(self, queue, app_config):
        super(AudioEncoderWorker, self).__init__()
        self.queue = queue
        self.app_config = app_config

    def run(self):
        while True:
            value = self.queue.get()
            if value is None:
                break
            language_pair, fn = value
            target_track_name = rf'{self.app_config["RitmomRoot"]}/audio/{language_pair}/audio{fn:03}.mp3'
            print(f'Encoding {target_track_name}')
            cmd_str = [
                rf'ffmpeg', '-y', '-i',
                rf'{self.app_config["RitmomRoot"]}/audio/{language_pair}/audio{fn:03}.wav',
                rf'-codec:a', 'libmp3lame', '-qscale:a', '2',
                target_track_name,
                rf'&&',
                rf'del',
                rf'{self.app_config["RitmomRoot"]}\audio\{language_pair}\audio{fn:03}.wav'
            ]
            pipe = Popen(cmd_str, shell=True, stdout=DEVNULL, stderr=STDOUT)
            out, err = pipe.communicate()
            pipe.wait()
            if not exists(target_track_name):
                print(f'Failed to create {target_track_name}')
                print(f'{str(err)}')

