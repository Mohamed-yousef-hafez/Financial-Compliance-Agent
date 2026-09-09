from pathlib import Path

from app.ingestion.loader import load_pdf
from app.ingestion.cleaner import clean_text
from app.ingestion.chunker import chunk_text


def build_documents(data_dir, tenant_id):
    tenant_path = Path(data_dir) / tenant_id

    if not tenant_path.exists():
        return []

    documents = []

    for pdf_path in tenant_path.rglob("*.pdf"):
        category = pdf_path.parent.name

        pages = load_pdf(pdf_path)

        for page_data in pages:
            text = clean_text(page_data["text"])

            if not text:
                continue

            chunks = chunk_text(text)

            for chunk_id, chunk in enumerate(chunks):
                metadata = {
                    "tenant_id": tenant_id,
                    "document_id": pdf_path.stem,
                    "source": pdf_path.name,
                    "category": category,
                    "page": page_data["page"],
                    "chunk_id": chunk_id,
                }

                documents.append(
                    {
                        "text": chunk,
                        "metadata": metadata,
                    }
                )

    return documents