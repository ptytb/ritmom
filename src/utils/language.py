
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0


def detect_language(text: str):
    languages = {
        'en': 'english',
        'fr': 'french',
        'ja': 'japanese',
        'ru': 'russian',
    }
    lang_langdetect = languages.get(detect(text), None)
    return lang_langdetect
