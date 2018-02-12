RITMOM - Repetition is the mother of memory.


### What this app does
It's for learning languages.
Creates audio tracks sourcing a word and phrase pairs from your Google Translate favorites list.

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


## TODO

- [ ] Arbitrary Text Source
- [X] Generate text output too
- [ ] Make a sequence configurable from a config
- [ ] Fix wordnet for languages differ from English
- [ ] Search for collocations
- [ ] Download missing NLTK packages and corpuses automatically if missing
- [X] Fix index before running tasks
- [X] Add synonyms and antonyms
- [X] Use more threads for TTS
- [X] Pickle indices for corpus for quicker start
- [X] Add wordnet: definition (thesaurus, examples, excerpts)
- [X] Update requirements.txt