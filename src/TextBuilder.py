from os import mkdir
from sys import modules
from src.postprocessing import *


class TextBuilder:
    def __init__(self, app_config):
        self.app_config = app_config
        self.extension = 'txt'
        self.stream = None
        self.text_jingles = app_config['text_jingles']
        self.postprocessing = app_config['postprocessing']

    def open(self, language_pair, track_num):
        try:
            mkdir(f'{self.app_config["RitmomRoot"]}/text/{language_pair}')
        except OSError:
            pass
        file_name = f'{self.app_config["RitmomRoot"]}/text/{language_pair}/audio{track_num:03}.{self.extension}'
        encoding = self.app_config['text_encoding'][language_pair] or 'urf-8'
        self.stream = open(file_name, mode='w', encoding=encoding, errors='ignore')

    def speak_with_postprocess(self, text, language_pair):
        module_list = list()

        for language in self.postprocessing:
            if language_pair.lower().startswith(language):
                module_list = self.postprocessing[language]
                break

        for module in module_list:
            if module.startswith('text') and module_list[module]:
                processed_text = modules[f'src.postprocessing.{module}'].process(text)
                print(processed_text, file=self.stream, sep='')

    def speak(self, text):
        print(text, file=self.stream, end='', sep='')

    def speak_jingle(self, jingle_name):
        print(self.text_jingles[jingle_name], file=self.stream, end='', sep='')


