from app.ingestion.cleaner import clean_text
from app.ingestion.chunker import chunk_text


def test_clean_text():
    assert clean_text("hello   world") == "hello world"


def test_chunk_text():
    text = " ".join(["word"] * 200)

    chunks = chunk_text(
        text,
        chunk_size=50,
        overlap=10,
    )

    assert len(chunks) > 1