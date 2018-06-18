from itertools import repeat
from operator import contains
from functools import partial
from comtypes.client import CreateObject

from src.SequenceDemultiplexor import SequenceDemultiplexor
from src.Sequencer import Sequencer, JingleChunk, SpeechChunk, FilterControlChunk
from src.PhraseExamples import PhraseExamples
from src.filter.AddVoice import AddVoice
from src.filter.PronounceByLetter import PronounceByLetter

from src.utils.config import split_name_pair


class SequenceBuilder:
    def __init__(self, *, app_config, encode_queue, only_wav, dump_sequencer_log):
        languages = app_config['languages']
        self.app_config = app_config
        self.dump_sequencer_log = dump_sequencer_log

        self.info_engine = CreateObject("SAPI.SpVoice")
        self.voices = dict()

        self.voices_com = voices = self.info_engine.GetVoices()
        for language_pair in languages:
            self.voices[language_pair] = dict()

            foreign_name, native_name = split_name_pair(language_pair)
            self.voices[language_pair]['native_name'] = native_name
            self.voices[language_pair]['foreign_name'] = foreign_name

            for purpose in languages[language_pair]:
                for i in range(voices.Count):
                    desc = voices.Item(i).GetDescription()
                    if desc.find(languages[language_pair][purpose]) != -1:
                        self.voices[language_pair][purpose] = i

            has_voice = partial(contains, self.voices[language_pair])
            assert all(map(has_voice, ['foreign1', 'foreign2', 'native']))

        self.phrase_examples = PhraseExamples(app_config)
        self.sequencer = Sequencer()
        self.chunk_demultiplexor = SequenceDemultiplexor(app_config, self.sequencer, encode_queue, only_wav)

    def make_audio_track(self, language_pair, lines, track_num):
        self.chunk_demultiplexor.start_section(language_pair, track_num)

        for word, translation in lines:
            if language_pair not in self.app_config['languages']:
                return

            native_name = self.voices[language_pair]['native_name']
            foreign_name = self.voices[language_pair]['foreign_name']

            # Say a phrase with both male and female narrators
            for voice_num in range(1, 3):
                first_pass = voice_num == 1
                voice_foreign = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                voice_native = self.voices_com.Item(self.voices[language_pair]['native'])
                self.sequencer << FilterControlChunk(instant=True,
                                                     target=AddVoice,
                                                     attribute='default_voices',
                                                     value={foreign_name: voice_foreign, native_name: voice_native})
                
                if first_pass:
                    self.sequencer << JingleChunk(jingle='timestamp')

                voice = voice_foreign

                self.sequencer << FilterControlChunk(instant=True, target=PronounceByLetter,
                                                     attribute='enabled', value=True)

                self.sequencer << SpeechChunk(text=word, language=foreign_name, final=not first_pass,
                                              rate=-6, volume=100, voice=voice, printable=first_pass)

                self.sequencer << FilterControlChunk(instant=True, target=PronounceByLetter,
                                                     attribute='enabled', value=False)

                self.sequencer << JingleChunk(jingle='silence_long', printable=first_pass)

                if translation:
                    # trans = trans.replace('~', word)
                    # trans = '; '.join(sorted(set(map(str.strip, trans.split(';')))))
                    for chunk in translation:
                        spoken = chunk.promote(SpeechChunk, rate=0, volume=60, printable=first_pass)
                        self.sequencer << spoken \
                                       << JingleChunk(jingle='silence', printable=first_pass)

                self.sequencer << JingleChunk(jingle='silence_long', printable=first_pass)

            word_info = self.phrase_examples.get_definitions_and_examples(word, foreign_name)
            if word_info:
                for voice_num in range(1, 3):
                    first_pass = voice_num == 1
                    voice_foreign = self.voices_com.Item(self.voices[language_pair][f'foreign{voice_num}'])
                    voice_native = self.voices_com.Item(self.voices[language_pair]['native'])
                    self.sequencer << FilterControlChunk(instant=True,
                                                         target=AddVoice,
                                                         attribute='default_voices',
                                                         value={foreign_name: voice_foreign, native_name: voice_native})

                    for definition in word_info.definitions:
                        voice = voice_foreign
                        if not isinstance(definition, JingleChunk):
                            definition = definition.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            definition.final = not first_pass
                        definition.printable = first_pass
                        self.sequencer << definition

                    for example in word_info.examples:
                        if not isinstance(example, JingleChunk):
                            if example.language == foreign_name:
                                voice = voice_foreign
                                volume = 100
                            else:
                                voice = voice_native
                                volume = 75
                            example = example.promote(SpeechChunk, rate=0, volume=volume, voice=voice, final=True)
                            example.final = not first_pass
                        example.printable = first_pass
                        self.sequencer << example

                    for synonym in word_info.synonyms:
                        voice = voice_foreign
                        if not isinstance(synonym, JingleChunk):
                            synonym = synonym.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            synonym.final = not first_pass
                        synonym.printable = first_pass
                        self.sequencer << synonym

                    for antonym in word_info.antonyms:
                        voice = voice_foreign
                        if not isinstance(antonym, JingleChunk):
                            antonym = antonym.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                            antonym.final = not first_pass
                        antonym.printable = first_pass
                        self.sequencer << antonym

                    excerpts = self.phrase_examples.search_excerpt(self.app_config, foreign_name, word)
                    if excerpts is not None:
                        for excerpt in excerpts:
                            if not isinstance(excerpt, JingleChunk):
                                voice = voice_foreign
                                excerpt = excerpt.promote(SpeechChunk, rate=0, volume=100, voice=voice, final=True)
                                excerpt.final = not first_pass
                            excerpt.printable = first_pass
                            self.sequencer << excerpt

            self.sequencer << JingleChunk(jingle='silence_long')
            self.sequencer << JingleChunk(jingle='silence_long', printable=False)

        self.sequencer << JingleChunk(jingle='end_of_part', volume=20)
        
        if self.dump_sequencer_log:
            def interleave_with_newline(iterator):
                for item in iterator:
                    yield item
                    yield '\n'

            sequencer_commands = map(repr, self.sequencer.queue)
            with open(f'text/{language_pair}/audio{track_num:03}.log', mode='wt', encoding='utf-8') as f:
                f.writelines(interleave_with_newline(reversed(list(sequencer_commands))))

        while len(self.sequencer):
            chunk = self.sequencer.pop()
            if chunk:
                self.chunk_demultiplexor.feed(chunk)

        self.chunk_demultiplexor.stop_section()
