import re
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile

from app.agents.agent import ComplianceAgent
from app.api.schemas import ChatRequest, ChatResponse, IngestRequest
from app.core.config import DATA_DIR
from app.core.security import (
    DEMO_USERS,
    UserContext,
    authenticate_demo_user,
    authorize,
    normalize_access_metadata,
)
from app.ingestion.pipeline import build_documents
from app.retrieval.retriever import Retriever
from app.retrieval.store import ChromaStore


app = FastAPI(
    title="Financial Compliance Agent",
    version="2.0.0",
)

store = ChromaStore()
retriever = Retriever(store)
agent = ComplianceAgent(retriever)


def validate_tenant_id(tenant_id: str) -> str:
    tenant_id = tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Tenant ID may contain only letters, numbers, underscores, and hyphens.",
        )
    return tenant_id


def validate_pdf_filename(filename: str) -> str:
    safe_filename = Path(filename).name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    if not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are supported: {safe_filename}",
        )
    return safe_filename


def get_current_user(x_demo_user: str | None) -> UserContext:
    try:
        return authenticate_demo_user(x_demo_user or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def require_tenant_owner(user: UserContext, tenant_id: str) -> None:
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Cross-tenant access is denied.",
        )


def parse_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_access_policy(
    access_scope: str,
    allowed_roles: list[str],
    allowed_users: list[str],
) -> dict:
    try:
        return normalize_access_metadata(
            {
                "access_scope": access_scope,
                "allowed_roles": allowed_roles,
                "allowed_users": allowed_users,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "financial-compliance-agent",
        "security": "permission-aware-rag",
    }


@app.get("/demo-users")
def demo_users():
    return {
        "users": [
            {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "roles": list(user.roles),
                "permissions": list(user.permissions),
            }
            for user in DEMO_USERS.values()
        ]
    }


@app.delete("/documents/{tenant_id}")
def clear_documents(
    tenant_id: str,
    x_demo_user: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user)
    tenant_id = validate_tenant_id(tenant_id)
    require_tenant_owner(user, tenant_id)

    try:
        authorize(user, "documents:write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    try:
        store.delete_documents(tenant_id=tenant_id)
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "files_deleted": 0,
            "message": "Tenant vectors cleared. Original documents were preserved.",
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
    access_scope: str = "tenant",
    allowed_roles: str | None = None,
    allowed_users: str | None = None,
    x_demo_user: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user)
    tenant_id = validate_tenant_id(tenant_id)
    require_tenant_owner(user, tenant_id)

    try:
        authorize(user, "documents:write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    roles = parse_csv_values(allowed_roles)
    users = parse_csv_values(allowed_users)
    policy = validate_access_policy(access_scope, roles, users)

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    tenant_dir = DATA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    uploaded_sources = []

    for uploaded_file in files:
        if not uploaded_file.filename:
            continue
        filename = validate_pdf_filename(uploaded_file.filename)
        content = await uploaded_file.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Empty file: {filename}")

        destination = tenant_dir / filename
        destination.write_bytes(content)
        saved_files.append(filename)
        uploaded_sources.append(filename)

    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    try:
        documents = build_documents(
            data_dir=DATA_DIR,
            tenant_id=tenant_id,
            selected_files=uploaded_sources,
            access_scope=policy["access_scope"],
            allowed_roles=policy["allowed_roles"],
            allowed_users=policy["allowed_users"],
        )

        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No readable text was found in the uploaded PDF files.",
            )

        document_ids = sorted(
            {item["metadata"]["document_id"] for item in documents}
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
            "access_policy": policy,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {exc}",
        )


@app.post("/ingest")
def ingest(
    request: IngestRequest,
    x_demo_user: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user)
    tenant_id = validate_tenant_id(request.tenant_id)
    require_tenant_owner(user, tenant_id)

    try:
        authorize(user, "documents:write")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    policy = validate_access_policy(
        request.access_scope,
        request.allowed_roles,
        request.allowed_users,
    )

    try:
        documents = build_documents(
            data_dir=DATA_DIR,
            tenant_id=tenant_id,
            access_scope=policy["access_scope"],
            allowed_roles=policy["allowed_roles"],
            allowed_users=policy["allowed_users"],
        )
        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No readable documents found for this tenant.",
            )

        sources = sorted({item["metadata"]["source"] for item in documents})
        document_ids = sorted({item["metadata"]["document_id"] for item in documents})
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
            "access_policy": policy,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_demo_user: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user)
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    try:
        return agent.run(question=question, user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
