RITMOM - Repetition is the mother of memory.


### What this app does
It's for learning languages. Creates audio tracks from:

- Your **Google Translate favorites** list. Feeds word and phrase pairs from.
- Plain text file with foreign word list. Offline dictionaries are used for translation.


The idea is to use a sequence

- foreign female slow
- native female normal
- example usage phrase female
- foreign male slow
- native female normal
- example usage phrase male

for better memorization.


### What it does not
Text to speech out of a box. It uses 3rd party TTS engines via Windows COM. You have to use
some proprietary TTS engine to generate a good quality narration.


## Usage

1. Install TTS engines
2. You will need *ffmpeg* executable in your PATH to convert your tracks to MP3.
3. Save phrases to `phrases/` dir, both *csv* or *xls* will fit:
![](doc/howto-google-translate.png)
4. `pip install -r requirements.txt`
5. Edit *config.json* file.

**foreign** and **native** parameters must contain substring of description, which can be listed
with this command: `python main.py -l`

Download desired text corpuses to be able to generate context usage phrases.
Corpuses are listed in a `phraseExamples` configuration option:

`import nltk; nltk.download()`

6. Generate audio `python main.py` 


#### Japanese support

For furigana support you'll need [MeCab](https://doc-0s-9o-docs.googleusercontent.com/docs/securesc/bfpns3k4jmfq4rerbchsjt9tvab2g2to/s1rba84ju4ebrtpunekt5uqhrcss5uuo/1518775200000/13553212398903315502/07793478864651846602/0B4y35FiV1wh7WElGUGt6ejlpVXc?e=download&nonce=vrph5sdvr9aks&user=07793478864651846602&hash=km3beiek9q72uomsoljre155mj7m4kkk) executable accessible in your PATH.

You'll need to install the requirements `pip install -r requirements-jp.txt`

#### Offline dictionaries

Supported dictionary formats:

- DSL (Used by [GoldenDict](https://goldendict.org/))
- LDX (Used by [ABBYY Lingvo]() and [Lingoes](https://www.lingoes.net))

## TODO

- [ ] Do try fuzzy matching if no translation found
- [X] Text: write approximate audio timestamp
- [ ] Arbitrary Text Source
- [X] Generate text output too
- [ ] Make a sequence configurable from a config
- [ ] Fix wordnet for languages differ from English
- [X] Search for collocations
- [ ] Download missing NLTK packages and corpuses automatically if missing
- [X] Fix index before running tasks
- [X] Add synonyms and antonyms
- [X] Use more threads for TTS
- [X] Pickle indices for corpus for quicker start
- [X] Add wordnet: definition (thesaurus, examples, excerpts)
- [X] Update requirements.txt
