import fitz


def load_pdf(path):
    document = fitz.open(path)
    pages = []

    try:
        for page_number, page in enumerate(document, start=1):
            pages.append(
                {
                    "page": page_number,
                    "text": page.get_text(),
                }
            )
    finally:
        document.close()

    return pages