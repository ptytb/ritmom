from src.translate.Dictionary import Dictionary
from src.utils.gzip_archive import get_uncompressed_size
from src.utils.term_progress import print_progressbar
import gzip
import re


class DslDictionary(Dictionary):
    """
    Manages loading, caching and translating with GoldenDict files (.dsl)
    """

    def __init__(self, file_path, encoding, cache_dir):
        super(DslDictionary, self).__init__(file_path, encoding, cache_dir, 'NAME')
        current_record = None
        file_size = get_uncompressed_size(file_path)

        with gzip.open(file_path, mode='rt', encoding=encoding) as f:
            while True:
                line = f.readline()
                if line is None or not line.startswith('#'):
                    break
                terms = re.match(r'#(?P<name>[^ ]+?) "(?P<value>[^"]+)"', line)
                self.dictionary_header[terms['name']] = terms['value']

            if self._load_cache():
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
                        self.dictionary_data[current_record['word']] = ' '.join(current_record['data'])
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
        self._save_cache()

    @staticmethod
    def _filter_formatting(text):
        dropout_tags = ['b', 'com', r'\*']
        for tag in dropout_tags:
            text = re.sub(rf'\[{tag}\].*?\[/{tag}\]', '', text)
        text = re.sub(r'\d+[.)]\s*', ';', text)  # numbered lists
        text = re.sub(rf'\\\[.*?\\\]', '', text)  # transcriptions
        text = re.sub(rf'\[.*?\]', '', text)  # tagged markup
        text = re.sub(rf'\s*\(\s*\)\s*', '', text)  # empty brackets
        text = re.sub(rf'^\s*;*', '', text)
        text = re.sub(rf'\s*;(\s*;)*\s*', '; ', text)
        return text.strip()


