from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
)

from app.core.config import DATA_DIR

from app.ingestion.pipeline import build_documents

from app.retrieval.store import ChromaStore
from app.retrieval.retriever import Retriever

from app.agents.agent import ComplianceAgent


app = FastAPI(
    title="Financial Compliance Agent",
    version="1.0.0",
)


store = ChromaStore()
retriever = Retriever(store)
agent = ComplianceAgent(retriever)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "financial-compliance-agent",
    }


@app.post("/upload")
async def upload_files(
    tenant_id: str,
    files: list[UploadFile] = File(...),
):
    tenant_dir = (
        DATA_DIR / tenant_id
    )

    tenant_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_files = []

    for file in files:
        if not file.filename:
            continue

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only PDF files are supported: "
                    f"{file.filename}"
                ),
            )

        destination = (
            tenant_dir / Path(file.filename).name
        )

        content = await file.read()

        destination.write_bytes(content)

        saved_files.append(
            destination.name
        )

    try:
        documents = build_documents(
            DATA_DIR,
            tenant_id,
        )

        count = store.upsert(documents)

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files_uploaded": saved_files,
            "chunks_indexed": count,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post("/ingest")
def ingest(request: IngestRequest):
    try:
        documents = build_documents(
            DATA_DIR,
            request.tenant_id,
        )

        count = store.upsert(documents)

        return {
            "status": "success",
            "tenant_id": request.tenant_id,
            "chunks_indexed": count,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):
    try:
        return agent.run(
            question=request.question,
            tenant_id=request.tenant_id,
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