import struct

from .Translator import Translator
import gzip
import re
import pickle
from os.path import exists


# Print iterations progress
def print_progressbar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = '\r')
    # Print New Line on Complete
    if iteration == total:
        print()


def get_uncompressed_size(filename):
    with open(filename, 'rb') as f:
        f.seek(-4, 2)
        return struct.unpack('I', f.read(4))[0]


class DslDictionary(Translator):

    def __init__(self, file_path, encoding, cache_dir):
        super(DslDictionary, self).__init__()

        self.dictionary = dict()
        self.dictionary_header = dict()
        current_record = None

        file_size = get_uncompressed_size(file_path)

        with gzip.open(file_path, mode='rt', encoding=encoding) as f:
            while True:
                line = f.readline()
                if line is None or not line.startswith('#'):
                    break
                terms = re.match(r'#(?P<name>[^ ]+?) "(?P<value>[^"]+)"', line)
                self.dictionary_header[terms['name']] = terms['value']

            if self._load_cache(cache_dir):
                return

            while True:
                line = f.readline()
                file_position = f.tell()
                reached_end = (file_size == file_position)

                if line is None or reached_end:
                    print_progressbar(file_position, file_size, f'Reading {self.dictionary_header["NAME"]}')
                    break

                line = line.strip()

                if line == '':
                    if current_record:
                        self.dictionary[current_record['word']] = current_record['data']
                        current_record = None
                    continue

                if current_record is None:
                    current_record = {"word": line, "data": list()}
                else:
                    current_record['data'].append(line)

                if file_position % 10000 == 0 or reached_end:
                    print_progressbar(file_position, file_size, f'Reading {self.dictionary_header["NAME"]}')

        print()
        print(f'Saving cache for {self.dictionary_header["NAME"]}')
        self._save_cache(cache_dir)

    def _save_cache(self, cache_dir):
        dictionary_cache_path = f'{cache_dir}/{self.dictionary_header["NAME"]}.dic'
        pickle.dump({"dictionary": self.dictionary, "dictionary_header": self.dictionary_header},
                    open(dictionary_cache_path, 'wb'))

    def _load_cache(self, cache_dir):
        dictionary_cache_path = f'{cache_dir}/{self.dictionary_header["NAME"]}.dic'
        cache_exists = exists(dictionary_cache_path)
        if cache_exists:
            cache = pickle.load(open(dictionary_cache_path, 'rb'))
            self.dictionary = cache['dictionary']
            self.dictionary_header = cache["dictionary_header"]
        return cache_exists

    @staticmethod
    def _filter_formatting(record):
        dropout_tags = ['b', 'com', r'\*']
        for tag in dropout_tags:
            record = re.sub(rf'\[{tag}\].*?\[/{tag}\]', '', record)
        record = re.sub(r'\d+[.)]\s*', '', record)  # numbered lists
        record = re.sub(rf'\\\[.*?\\\]', '', record)  # transcriptions
        record = re.sub(rf'\[.*?\]', '', record)  # tagged markup
        record = re.sub(rf'\s*\(\s*\)\s*', '', record)  # empty brackets
        return record.strip()

    def translate_word(self, word):
        try:
            items = self.dictionary[word]
        except KeyError:
            return None

        return self._filter_formatting(' '.join(items))
