from attr import evolve

from src.filter.BaseFilter import BaseFilter


class AddVoice(BaseFilter):
    
    def __init__(self):
        super().__init__()
        self.default_voices = None

    def __call__(self, chunk):
        from src.Sequencer import SpeechChunk
        result = list()
        
        if isinstance(chunk, SpeechChunk) and chunk.voice is None:
            result.append(evolve(chunk, voice=self.default_voices[chunk.language]))
        else:
            result.append(self._duplicate_chunk(chunk))

        return result
