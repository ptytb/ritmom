import re
import struct
import mmap
import zlib
from collections import namedtuple

from src.utils.term_progress import print_progressbar
from .Dictionary import Dictionary


IndexData = namedtuple('IndexData', [
    'last_word_pos',
    'last_xml_pos',
    'dummy',
    'refs',
    'current_word_offset',
    'current_xml_offset',
])


class LdxDictionary(Dictionary):
    def __init__(self, file_path, encoding, cache_dir):
        super().__init__(file_path, encoding, cache_dir, 'id')

        with open(file_path, 'r+b') as f:
            with mmap.mmap(f.fileno(), 0) as mm:
                self.mm = mm
                self.position = 0
                self._read_header()

    def get_int(self, offset, *, unsigned=False, buffer=None):
        return struct.unpack('I' if unsigned else 'i', (buffer or self.mm)[offset:offset+4])[0]

    def get_short(self, offset, *, buffer=None):
        return struct.unpack('h', (buffer or self.mm)[offset:offset+2])[0]

    def _read_header(self):
        self.dictionary_header['type'] = str(self.mm[1:4], encoding='utf-8', errors='ignore')
        self.dictionary_header['version'] = f"{self.get_short(0x18)}.{self.get_short(0x1A)}"
        self.dictionary_header['id'] = hex(self.get_int(0x1C, unsigned=True))
        self.dictionary_header['data_offset'] = self.get_int(0x5C) + 0x60

        if self._load_cache():
            return

        if self.mm.size() > self.dictionary_header['data_offset']:
            self.dictionary_header['dictionary_type'] = self.get_int(self.dictionary_header['data_offset'])
            offset_with_info = self.get_int(self.dictionary_header['data_offset'] + 4) + self.dictionary_header['data_offset'] + 12

            if self.dictionary_header['dictionary_type'] == 3:
                self._read_dictionary(self.dictionary_header['data_offset'])
            elif self.mm.size() > offset_with_info - 0x1C:
                self._read_dictionary(offset_with_info)
            else:
                raise Exception(f'No dictionary in this LDX: {self.file_path}')

        self._save_cache()

    def _read_dictionary(self, offset: int):
        self.dictionary_header['limit'] = self.get_int(offset + 4) + offset + 8
        self.dictionary_header['index_offset'] = offset + 0x1C
        self.dictionary_header['compressed_data_header_offset'] = self.get_int(offset + 8) + self.dictionary_header['index_offset']
        self.dictionary_header['inflated_words_index_length'] = self.get_int(offset + 12)
        self.dictionary_header['inflated_words_length'] = self.get_int(offset + 16)
        self.dictionary_header['inflated_xml_length'] = self.get_int(offset + 20)
        self.dictionary_header['definitions'] = (self.dictionary_header['compressed_data_header_offset'] - offset) // 4

        deflate_streams = list()
        self.position = self.dictionary_header['compressed_data_header_offset'] + 8
        stream_offset = self.get_int(self.position)
        self.position += 4
        while stream_offset + self.position < self.dictionary_header['limit']:
            stream_offset = self.get_int(self.position)
            deflate_streams.append(stream_offset)
            self.position += 4

        compressed_data_offset = self.position
        self.dictionary_header['streams'] = len(deflate_streams)

        inflated_data = bytearray()
        self._inflate_data(deflate_streams, inflated_data)

        if len(inflated_data):
            self._extract(inflated_data)

        self._save_cache()

    def _inflate_data(self, deflate_streams, inflated_data):
        start_offset = self.position
        offset = -1
        last_offset = start_offset

        for relative_offset in deflate_streams:
            offset = start_offset + relative_offset
            try:
                data = zlib.decompress(self.mm[last_offset:offset])
                inflated_data += data
            except OSError as e:
                print(f'Stream @{offset} {e}')
            else:
                ...
            last_offset = offset

    def _extract(self, inflated_data):
        definitions_offset = self.dictionary_header['inflated_words_index_length']
        xml_offset = definitions_offset + self.dictionary_header['inflated_words_length']

        data_len = 10
        total_definitions = (definitions_offset // data_len) - 1

        for i in range(0, total_definitions):
            index_data, definition_data = self._read_definition_data(inflated_data, definitions_offset, xml_offset, data_len, i)
            word, info = definition_data[0], definition_data[1]
            self.dictionary_data[word] = info
            if i % 5000 == 0:
                print_progressbar(i, total_definitions, f"Reading LDX {self.dictionary_header['id']}")

    def _read_definition_data(self, inflated_data, definitions_offset, xml_offset, data_len, i):
        index_data = self._get_index_data(inflated_data, data_len * i)
        last_word_pos = index_data.last_word_pos
        current_word_offset = index_data.current_word_offset
        xml = str(inflated_data[xml_offset + index_data.last_xml_pos:xml_offset+index_data.current_xml_offset], encoding='utf-8', errors='ignore')
        refs = index_data.refs
        while refs > 0:
            ref = self.get_int(definitions_offset + index_data.last_word_pos, buffer=inflated_data)
            index_data = self._get_index_data(inflated_data, data_len * ref)
            xml_chunk = inflated_data[xml_offset + index_data.last_xml_pos:xml_offset + index_data.current_xml_offset]
            if len(xml) == 0:
                xml = xml_chunk
            else:
                xml = f'{xml_chunk}, {xml}'
            last_word_pos += 4

        word = str(inflated_data[definitions_offset + last_word_pos:definitions_offset + current_word_offset], encoding='utf-8', errors='ignore')
        definition_data = word, xml
        return index_data, definition_data

    def _get_index_data(self, inflated_data, offset):
        return IndexData(
            self.get_int(offset, buffer=inflated_data),
            self.get_int(offset+4, buffer=inflated_data),
            inflated_data[8],
            inflated_data[9],
            self.get_int(offset+10, buffer=inflated_data),
            self.get_int(offset+14, buffer=inflated_data),
        )

    @staticmethod
    def _filter_formatting(text):
        dropout_tags = ['U', 'M']
        for tag in dropout_tags:
            text = re.sub(rf'<{tag}>.*?</{tag}>', '', text)
        text = re.sub(r'<[^>]+?>', '', text)  # markup
        text = re.sub(r'^[^|]*\|\|[^.]*\.', '', text)  # transcription
        text = re.sub(r'\s*\[[^]]*]', '', text)  # special domain demarcation
        return text
