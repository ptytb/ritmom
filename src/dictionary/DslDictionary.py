from abc import ABC, abstractmethod
from collections import deque
import gzip
import re
from typing import List

from src.dictionary.BaseDictionary import BaseDictionary
from src.utils.gzip_archive import get_uncompressed_size
from src.utils.term_progress import print_progressbar


class DslMarkup:
    """
    Parses DSL dictionary info record and keeps tree structure (XML-like thingy)
    """

    class DslMarkupSelector:
        """
        Utility for getting item from parsed DSL (*DslMarkup* instance),
        or converting it to plain text.
        Picked child items will be wrapped with *DslMarkupSelector* as well.
        """
        
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
    
    def inner_text(self):
        return self.DslMarkupSelector._inner_text(self.root)
    
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

            attributes = dict()
            if is_tag_open:
                for pair in tag_parts[1:]:
                    eq_pos = pair.find('=')
                    key = pair[:eq_pos]
                    value = pair[eq_pos + 1:]
                    attributes[key] = value.strip('"')
            else:
                tag_name = tag_name[1:]  # remove heading '/'
                
            token = {"type": "tag" if is_tag_open else "tag_close",
                     "tag": tag_name,
                     "attributes": attributes}
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


class DslMarkupWalker(ABC):
    """
    Traverses *DslMarkup* instance and runs callbacks.
    Subclass me and redefine desired callbacks.
    """
    
    def __init__(self, ignore_tags):
        self._ignore_tags = ignore_tags
        
    @abstractmethod
    def on_begin(self):
        ...
    
    @abstractmethod
    def on_end(self):
        ...

    @abstractmethod
    def on_tag(self, tag, attributes):
        ...

    @abstractmethod
    def on_tag_close(self, tag):
        ...

    @abstractmethod
    def on_text(self, text):
        ...

    def _traverse(self, root):
        for child in root:
            if child['type'] == 'text':
                self.on_text(child['value'])
            elif child['type'] == 'tag' and child['tag'] not in self._ignore_tags:
                self.on_tag(child['tag'], child['attributes'])
                self._traverse(child['children'])
                self.on_tag_close(child['tag'])

    def walk(self, dsl_markup: DslMarkup):
        self.on_begin()
        self._traverse(dsl_markup.root)
        self.on_end()


class ChopperWalker(DslMarkupWalker):
    """
    Traverses to the *DslMarkupWalker* instance and chops a dictionary info record into
    the language-tagged pieces of text, which're actually being instanced
    with *factory*
    """
    
    def __init__(self, ignore_tags, factory, default_language):
        """
        
        :param ignore_tags: Iterable containing tags we are not interested in
        :param factory: Factory callable takes kwargs: text, language
        :param default_language: Supposed to be the *native_language* of the dictionary
        """
        super().__init__(ignore_tags)
        self.factory = factory
        self.default_language = default_language
        self.chunks = list()
        self.accumulated_text = ''
        self.current_language = default_language
    
    def _flush_chunk(self):
        if self.accumulated_text:
            self.chunks.append(self.factory(language=self.current_language,
                                            text=self.accumulated_text))
        self.accumulated_text = ''
        self.current_language = self.default_language

    def on_begin(self):
        ...

    def on_end(self):
        self._flush_chunk()

    def on_tag(self, tag, attributes):
        if tag == 'lang':
            self._flush_chunk()
            self.current_language = attributes['name'].lower()

    def on_tag_close(self, tag):
        if tag == 'lang':
            self._flush_chunk()

    def on_text(self, text):
        self.accumulated_text += text


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

    def translate_word_chunked(self, word, chunk_factory) -> List:
        word_info = self.get_raw_word_info(word)
        if word_info is None:
            return list()
        word_info = word_info.replace('~', word)  # '~' means the substitute for word we sought for
        markup = DslMarkup(word_info)
        walker = ChopperWalker(ignore_tags={'b'}, factory=chunk_factory, default_language=self.native_language)
        walker.walk(markup)
        return walker.chunks

