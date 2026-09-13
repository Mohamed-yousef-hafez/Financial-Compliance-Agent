from pathlib import Path
import hashlib

from app.ingestion.loader import load_pdf
from app.ingestion.cleaner import clean_text
from app.ingestion.chunker import chunk_text


def get_file_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(block)

    return hasher.hexdigest()[:16]


def build_documents(data_dir, tenant_id, selected_files=None):
    tenant_path = Path(data_dir) / tenant_id

    if not tenant_path.exists():
        return []

    documents = []

    pdf_files = list(tenant_path.rglob("*.pdf"))

    if selected_files is not None:
        selected_names = {
            Path(name).name
            for name in selected_files
        }

        pdf_files = [
            pdf_path
            for pdf_path in pdf_files
            if pdf_path.name in selected_names
        ]

    for pdf_path in pdf_files:
        file_hash = get_file_hash(pdf_path)
        document_id = f"{pdf_path.stem}_{file_hash}"
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
                    "document_id": document_id,
                    "source": pdf_path.name,
                    "category": category,
                    "page": page_data["page"],
                    "chunk_id": chunk_id,
                    "file_hash": file_hash,
                }

                documents.append(
                    {
                        "text": chunk,
                        "metadata": metadata,
                    }
                )

    return documents