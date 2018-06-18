from attr import evolve

from src.filter.BaseFilter import BaseFilter
from re import match


class SplitMixedLanguages(BaseFilter):
    
    def __call__(self, chunk):
        from src.Sequencer import TextChunk, SpeechChunk, JingleChunk

        result = list()
        original = chunk
        
        if isinstance(chunk, TextChunk):
            current_language = None
            buffer = ''
            
            n_last = len(chunk.text) - 1
            n_cuts = 0
            for n, char in enumerate(chunk.text):
                language = self._get_language(char)
                if current_language is None:
                    current_language = language
                elif current_language != language and language is not None or n == n_last:
                    if n_cuts:
                        result.append(JingleChunk(jingle='silence'))
                    text = buffer + char if n == n_last else buffer
                    changes = {"text": text, "language": current_language}
                    if isinstance(original, SpeechChunk):
                        voice = chunk.voice if chunk.language == current_language else None
                        evolved = evolve(chunk, **changes, voice=voice)
                        result.append(evolved)
                    else:
                        result.append(TextChunk(**changes))
                    current_language = language
                    buffer = ''
                    n_cuts += 1
                buffer += char
        else:
            result.append(self._duplicate_chunk(chunk))
        
        return result
    
    @staticmethod
    def _get_language(char):
        n = ord(char)
        if 'a' <= char <= 'z' and 'A' <= char <= 'z':
            return 'english'
        elif match(r'[а-яА-Я]', char):
            return 'russian'
        elif '\u30A0' <= char <= '\u30FF' or '\u3040' <= char <= '\u309F':  # Katakana and Hiragana blocks
            return 'japanese'
        else:
            return None
