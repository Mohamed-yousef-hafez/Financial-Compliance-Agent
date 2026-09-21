import re


def clean_text(text):
    if not isinstance(text, str):
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()