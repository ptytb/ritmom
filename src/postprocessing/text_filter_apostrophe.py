from re import sub


def process(text: str):
    return sub(r"^['`\"]+|['`\"]+$", '', text)
