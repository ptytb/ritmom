import re


def split_name_pair(language_pair):
    i = list(re.finditer(r'[A-Z]', language_pair))[1].span()[0]
    return language_pair[:i].lower(), language_pair[i:].lower()
