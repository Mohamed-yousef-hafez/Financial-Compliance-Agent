from pathlib import Path
import hashlib

from app.core.security import access_flag_key, normalize_access_metadata
from app.ingestion.loader import load_pdf
from app.ingestion.cleaner import clean_text
from app.ingestion.chunker import chunk_text


def get_file_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()[:16]


def build_documents(
    data_dir,
    tenant_id,
    selected_files=None,
    access_scope="tenant",
    allowed_roles=None,
    allowed_users=None,
):
    tenant_path = Path(data_dir) / tenant_id
    if not tenant_path.exists():
        return []

    access_template = normalize_access_metadata(
        {
            "access_scope": access_scope,
            "allowed_roles": allowed_roles or [],
            "allowed_users": allowed_users or [],
        }
    )

    documents = []
    pdf_files = list(tenant_path.rglob("*.pdf"))

    if selected_files is not None:
        selected_names = {Path(name).name for name in selected_files}
        pdf_files = [pdf for pdf in pdf_files if pdf.name in selected_names]

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
                    "access_scope": access_template["access_scope"],
                    "allowed_roles": ",".join(access_template["allowed_roles"]),
                    "allowed_users": ",".join(access_template["allowed_users"]),
                }

                for role in access_template["allowed_roles"]:
                    metadata[access_flag_key("access_role", role)] = True
                for allowed_user in access_template["allowed_users"]:
                    metadata[access_flag_key("access_user", allowed_user)] = True
                documents.append({"text": chunk, "metadata": metadata})

    return documents
