from collections import deque
import gzip
import re

from src.dictionary.BaseDictionary import BaseDictionary
from src.utils.gzip_archive import get_uncompressed_size
from src.utils.term_progress import print_progressbar


class DslMarkup:

    class DslMarkupSelector:
        def __init__(self, root):
            self.root = root

        def __getitem__(self, item):
            t = type(item)
            if t == str:
                return [__class__(e) for e in self.root if e['type'] == 'tag' and e['tag'] == item]
            elif t in (int, slice):
                return __class__(self.root[item])

        @staticmethod
        def _inner_text(root, _children=None):
            children = _children or list()
            for child in root:
                if child['type'] == 'text':
                    children.append(child['value'])
                elif child['type'] == 'tag':
                    __class__._inner_text(child['children'], children)
                else:
                    raise BaseException()
            return ''.join(children)

        def inner_text(self):
            if self.root['type'] == 'tag':
                return self._inner_text(self.root['children'])
            elif self.root['type'] == 'text':
                return self.root['value']
            else:
                raise BaseException()

    def __init__(self, text):
        tokens = self._tokenize_markup(text)
        markup = self._parse_markup(tokens)
        self.root = markup

    def __getitem__(self, item):
        selector = self.DslMarkupSelector(self.root)
        return selector[item]

    @staticmethod
    def _consume_token(text: str):
        tag_pos = text.find('[')

        while tag_pos > 0:
            if text[tag_pos - 1] == '\\':
                tag_pos = text.find('[', tag_pos + 1)
            else:
                break

        if tag_pos == 0:
            tag_end_pos = text.find(']')
            tag_parts = re.split(r'\s+', text[1:tag_end_pos])
            tag_name = tag_parts[0]
            is_tag_open = not tag_name.startswith('/')
            if not is_tag_open:
                tag_name = tag_name[1:]  # remove heading '/'
            token = {"type": "tag" if is_tag_open else "tag_close",
                     "tag": tag_name,
                     "attributes": tag_parts[1 if is_tag_open else 2:]}
            remainder = text[tag_end_pos+1:]
        else:
            tag_pos = tag_pos if tag_pos != -1 else len(text)
            token = {"type": "text", "value": text[:tag_pos]}
            remainder = text[tag_pos:]
        return token, remainder

    @staticmethod
    def _tokenize_markup(text):
        tokens = list()
        while text:
            token, text = __class__._consume_token(text)
            tokens.append(token)
        return tokens

    @staticmethod
    def _parse_markup(tokens):
        true_root = root = list()
        node_stack = deque()
        for token in tokens:
            if token['type'] == 'tag':
                root.append(token)
                children = token['children'] = list()
                node_stack.append(root)
                root = children
            elif token['type'] == 'tag_close':
                root = node_stack.pop()
            elif token['type'] == 'text':
                root.append(token)
        return true_root


class DslBaseDictionary(BaseDictionary):
    """
    Manages loading, caching and translating with GoldenDict files (.dsl)
    """

    def __init__(self, file_path, encoding, cache_dir):
        super(DslBaseDictionary, self).__init__(file_path, encoding, cache_dir, 'NAME')
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

    def get_examples(self, word):
        phrases = []
        word_info = self[word]
        if not word_info:
            return phrases
        examples = re.findall(r'\[ex\](.*?)\[/ex\]', word_info)
        for e in examples:
            phrase_marked = e.replace('~', word)  # '~' means the substitute for word we sought for
            markup = DslMarkup(phrase_marked)
            lang = markup['lang'][0].inner_text()  # the first for example
            trans = ''.join([m.inner_text() for m in markup[1:]])  # the rest for translation
            phrases.append((lang, trans))
        return phrases

