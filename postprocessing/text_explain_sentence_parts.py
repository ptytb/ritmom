from rakutenma import RakutenMA

# Initialize a RakutenMA instance with an empty model
# the default ja feature set is set already
rma = RakutenMA()

# Initialize a RakutenMA instance with a pre-trained model
rma = RakutenMA(phi=1024, c=0.007812)  # Specify hyperparameter for SCW (for demonstration purpose)
rma.load('D:\Downloads\model_ja.json')


def process(text):
    tokens = rma.tokenize(text)
    return ' '.join(map(lambda pair: f'{pair[0]} ({pair[1]})', tokens))
