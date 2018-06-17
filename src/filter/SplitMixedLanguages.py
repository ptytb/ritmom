from src.filter.BaseFilter import BaseFilter
from re import match


class SplitMixedLanguages(BaseFilter):
    
    def __call__(self, chunk):
        from src.Sequencer import TextChunk
        result = list()
        
        if isinstance(chunk, TextChunk):
            current_language = None
            buffer = ''
            
            n_last = len(chunk.text) - 1
            for n, char in enumerate(chunk.text):
                language = self._get_language(char)
                if current_language is None:
                    current_language = language
                elif current_language != language and language is not None or n == n_last:
                    text = buffer + char if n == n_last else buffer
                    result.append(TextChunk(text=text, language=current_language))
                    current_language = language
                    buffer = ''
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
            
            
