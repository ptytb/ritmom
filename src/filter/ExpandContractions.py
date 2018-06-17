from src.Sequencer import TextChunk
from src.filter.BaseFilter import BaseFilter
from re import sub


class ExpandContractions(BaseFilter):

    contractions = {
        "english": {
            "smb": "somebody",
            "smth": "something"
        },
        "russian": {
            "кто-л": "кто-либо",
            "кого-л": "кого-либо",
            "кому-л": "кому-либо",
            "кем-л": "кем-либо",
            "ком-л": "ком-либо",
            "что-л": "что-либо",
            "чему-л": "чему-либо",
            "чем-л": "чем-либо",
            "чём-л": "чём-либо",
        }
    }
    
    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        result = [chunk]
        if isinstance(chunk, TextChunk) and chunk.language in self.contractions:
            contractions = self.contractions[chunk.language]
            for abbr in contractions:
                chunk.text = sub(f'{abbr}.', contractions[abbr], chunk.text)
        return result
