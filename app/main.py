import re
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.agents.agent import ComplianceAgent
from app.api.schemas import ChatRequest, ChatResponse, IngestRequest
from app.core.config import DATA_DIR
from app.ingestion.pipeline import build_documents
from app.retrieval.retriever import Retriever
from app.retrieval.store import ChromaStore


app = FastAPI(
    title="Financial Compliance Agent",
    version="1.1.0",
)


store = ChromaStore()
retriever = Retriever(store)
agent = ComplianceAgent(retriever)


def validate_tenant_id(tenant_id: str) -> str:
    tenant_id = tenant_id.strip()

    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Tenant ID is required.",
        )

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant_id):
        raise HTTPException(
            status_code=400,
            detail=(
                "Tenant ID may contain only letters, "
                "numbers, underscores, and hyphens."
            ),
        )

    return tenant_id


def validate_pdf_filename(filename: str) -> str:
    safe_filename = Path(filename).name

    if not safe_filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid file name.",
        )

    if not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only PDF files are supported: "
                f"{safe_filename}"
            ),
        )

    return safe_filename


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "financial-compliance-agent",
    }

@app.delete("/documents")
def clear_documents(tenant_id: str):
    tenant_id = validate_tenant_id(tenant_id)

    try:
        store.delete_documents(
            tenant_id=tenant_id
        )

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files_deleted": 0,
            "message": (
                "Tenant vectors cleared. "
                "Original PDF files were preserved."
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear tenant vectors: {exc}",
        )
    
        

@app.post("/upload")
async def upload_files(
    tenant_id: str,
    files: list[UploadFile] = File(...),
):
    tenant_id = validate_tenant_id(tenant_id)

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required.",
        )

    tenant_dir = DATA_DIR / tenant_id

    tenant_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_files = []
    uploaded_sources = []

    for uploaded_file in files:
        if not uploaded_file.filename:
            continue

        filename = validate_pdf_filename(
            uploaded_file.filename
        )

        content = await uploaded_file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail=f"Empty file: {filename}",
            )

        destination = tenant_dir / filename
        destination.write_bytes(content)

        saved_files.append(filename)
        uploaded_sources.append(filename)

    if not saved_files:
        raise HTTPException(
            status_code=400,
            detail="No valid files were uploaded.",
        )

    try:
        documents = build_documents(
            data_dir=DATA_DIR,
            tenant_id=tenant_id,
            selected_files=uploaded_sources,
        )

        if not documents:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text was found in "
                    "the uploaded PDF files."
                ),
            )

        document_ids = sorted(
            {
                item["metadata"]["document_id"]
                for item in documents
            }
        )

        chunks_indexed = store.replace_documents(
            documents=documents,
            tenant_id=tenant_id,
            document_ids=document_ids,
            sources=uploaded_sources,
        )

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files_uploaded": saved_files,
            "files_processed": len(saved_files),
            "chunks_indexed": chunks_indexed,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {exc}",
        )


@app.post("/ingest")
def ingest(request: IngestRequest):
    tenant_id = validate_tenant_id(
        request.tenant_id
    )

    try:
        documents = build_documents(
            data_dir=DATA_DIR,
            tenant_id=tenant_id,
        )

        if not documents:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable documents found "
                    "for this tenant."
                ),
            )

        sources = sorted(
            {
                item["metadata"]["source"]
                for item in documents
            }
        )

        document_ids = sorted(
            {
                item["metadata"]["document_id"]
                for item in documents
            }
        )

        chunks_indexed = store.replace_documents(
            documents=documents,
            tenant_id=tenant_id,
            document_ids=document_ids,
            sources=sources,
        )

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files_processed": len(sources),
            "files": sources,
            "chunks_indexed": chunks_indexed,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {exc}",
        )
    
  

@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):
    tenant_id = validate_tenant_id(
        request.tenant_id
    )

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question is required.",
        )

    try:
        return agent.run(
            question=question,
            tenant_id=tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )