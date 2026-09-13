import re


def tokenize(text):
    return set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text.lower(),
        )
    )


def token_overlap(question, document):
    question_tokens = tokenize(question)
    document_tokens = tokenize(document)

    if not question_tokens:
        return 0.0

    return len(
        question_tokens & document_tokens
    ) / len(question_tokens)


def hybrid_score(vector_score, lexical_score):
    return (
        0.75 * vector_score
        + 0.25 * lexical_score
    )