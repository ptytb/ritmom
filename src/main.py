# coding: utf-8

from itertools import chain

from multiprocessing.pool import Pool
from multiprocessing import Manager

from traceback import print_exc

from comtypes.client import CreateObject

from datetime import datetime, timedelta

from os.path import abspath
from os import cpu_count
from json import load
import re
import argparse

from typing import Dict

from AudioBuilder import AudioBuilder
from AudioEncoderWorker import AudioEncoderWorker
from WordNetCache import WordNetCache
from pathtools.path import parent_dir_path

from source.csv import CsvSource
from source.excel import ExcelSource

from src.source.util import UnrollMultilineCell


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


def init_audio_builder(_encode_queue, _app_config, _lock, _only_wav):
    """
    This will initialize a worker process
    :param _encode_queue:
    :param _app_config:
    :param _lock:
    :return:
    """
    global audio_builder
    app_config = _app_config
    WordNetCache._lock = _lock
    audio_builder = AudioBuilder(app_config=app_config,
                                 encode_queue=_encode_queue,
                                 only_wav=_only_wav)


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
    ritmom_root = parent_dir_path(parent_dir_path(abspath(__file__)))

    def load_config():
        config = load(open(f'{ritmom_root}/config.json'))
        languages = config['languages']
        filtered_languages = dict()
        for language, props in languages.items():
            if 'ignore' not in props or not props['ignore']:
                filtered_languages[language] = {prop: props[prop] for prop in props if prop != 'ignore'}
        config['languages'] = filtered_languages
        return config

    def main():
        parser = argparse.ArgumentParser()
        parser.add_argument('-l', help='List voice engines', action='store_true')
        parser.add_argument('-w', help='Write WAV only, skip conversion to MP3', action='store_true')
        parser.add_argument('-s', help='Start RPC server', action='store_true')
        args = parser.parse_args()

        if args.l:
            list_engines()
            exit(0)

        time_start = datetime.utcnow()

        app_config = load_config()
        app_config['RitmomRoot'] = ritmom_root

        phrasebooks = [
            UnrollMultilineCell(default_language=app_config['default'])(
                next(get_source(f"{app_config['RitmomRoot']}/{book}")))
            for book in app_config['phrasebooks']
        ]
        phrasebook = chain(*phrasebooks)

        with Manager() as multiprocessing_manager:
            _lock = multiprocessing_manager.Lock()

            encode_queue = multiprocessing_manager.Queue()
            encode_worker = AudioEncoderWorker(encode_queue, app_config)
            encode_worker.start()

            with Pool(processes=cpu_count() - 2,
                      initializer=init_audio_builder,
                      initargs=(encode_queue, app_config, _lock, args.w)) as pool:

                builder_queue: Dict[str, list] = dict()
                builder_parts: Dict[str, int] = dict()

                def process_chunk():
                    pool.apply_async(make_audio_track, (language_pair,
                                                        builder_queue.pop(language_pair),
                                                        builder_parts[language_pair]))

                    builder_queue[language_pair] = list()
                    builder_parts[language_pair] += 1

                for language_pair, word, trans in phrasebook:
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

        elapsed: timedelta = datetime.utcnow() - time_start
        print(f'time taken: {elapsed.total_seconds()} sec')

    main()
