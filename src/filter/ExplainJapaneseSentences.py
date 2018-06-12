from src.Sequencer import Chunk, TextChunk
from src.filter.BaseFilter import BaseFilter

from os.path import abspath

from rakutenma import RakutenMA


class ExplainJapaneseSentences(BaseFilter):

    def __init__(self):
        super().__init__()
        
        # Initialize a RakutenMA instance with an empty model
        # the default ja feature set is set already
        self.rma = RakutenMA()

        # Initialize a RakutenMA instance with a pre-trained model
        self.rma = RakutenMA(phi=1024, c=0.007812)  # Specify hyperparameter for SCW (for demonstration purpose)

        # https://github.com/ikegami-yukino/rakutenma-python/tree/master/rakutenma/model
        self.rma.load(abspath(r'..\resource\model_ja.min.json'))

    def __call__(self, chunk):
        chunk = self._duplicate_chunk(chunk)
        chunk.final = True

        result = [chunk]
        text = self.tokenize(chunk.text)
        result.append(TextChunk(text=text, language='japanese', audible=False, printable=True, final=True))
        return result

    def tokenize(self, text):
        tokens = self.rma.tokenize(text)
        return ' '.join(map(lambda pair: f'{pair[0]} ({pair[1]})', tokens))

