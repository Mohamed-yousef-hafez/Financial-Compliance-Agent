import re
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agents.agent import ComplianceAgent
from app.api.schemas import ChatRequest, ChatResponse, IngestRequest
from app.core.auth import (
    AuthProviderUnavailable,
    InvalidAccessToken,
    verify_supabase_access_token,
)
from app.core.config import (
    APP_ENV,
    AUTH_MODE,
    CORS_ALLOWED_ORIGINS,
    DATA_DIR,
    MAX_UPLOAD_BYTES,
    REPO_DATA_DIR,
)
from app.core.security import (
    DEMO_USERS,
    UserContext,
    authenticate_demo_user,
    authorize,
    normalize_access_metadata,
)
from app.ingestion.pipeline import build_documents
from app.retrieval.retriever import Retriever
from app.retrieval.store import SupabaseVectorStore
import logging
logger = logging.getLogger(__name__)
if APP_ENV == "production" and AUTH_MODE != "supabase_jwt":
    raise RuntimeError(
        "Production requires AUTH_MODE=supabase_jwt"
    )
app = FastAPI(
    title="Financial Compliance Agent",
    version="2.1.0",
    description="Multi-tenant evidence-grounded compliance assistant",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Demo-User"],
)

store = SupabaseVectorStore()
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
    # Reject path-like names rather than trusting platform-dependent basename rules.
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    safe_filename = Path(filename).name
    if not safe_filename or not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )
    return safe_filename


def get_current_user(
    x_demo_user: str | None,
    authorization: str | None,
) -> UserContext:
    if AUTH_MODE == "demo":
        try:
            return authenticate_demo_user(x_demo_user or "")
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if AUTH_MODE != "supabase_jwt":
        raise HTTPException(status_code=503, detail="Authentication mode is unavailable.")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="A valid Supabase Bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = authorization.split(" ", 1)[1].strip()
    try:
        auth_user_id = verify_supabase_access_token(access_token)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=401,
            detail="Access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthProviderUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Identity provider is temporarily unavailable.",
        ) from exc

    try:
        user = store.get_user_context(auth_user_id)
    except Exception as exc:
        # Never return SQL connection strings or database exception details to clients.
        raise HTTPException(
            status_code=503,
            detail="User access registry is temporarily unavailable.",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=403,
            detail="This account is not assigned to an active tenant.",
        )
    return user


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def require_permission(user: UserContext, permission: str) -> None:
    try:
        authorize(user, permission)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "financial-compliance-agent",
        "authentication_mode": AUTH_MODE,
        "database": "supabase-pgvector",
    }


@app.get("/me")
def me(
    x_demo_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user, authorization)
    return {
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "roles": list(user.roles),
        "permissions": list(user.permissions),
        "auth_mode": AUTH_MODE,
    }


@app.get("/demo-users")
def demo_users():
    if AUTH_MODE != "demo":
        raise HTTPException(status_code=404, detail="Not found")
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
    authorization: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user, authorization)
    tenant_id = validate_tenant_id(tenant_id)
    require_tenant_owner(user, tenant_id)
    require_permission(user, "documents:delete")

    try:
        store.delete_documents(tenant_id=tenant_id, user=user)
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "message": "Tenant vectors cleared. Original PDFs were not deleted.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to clear tenant vectors.",
        ) from exc


@app.post("/upload")
async def upload_files(
    tenant_id: str,
    files: list[UploadFile] = File(...),
    access_scope: str = "tenant",
    allowed_roles: str | None = None,
    allowed_users: str | None = None,
    x_demo_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user, authorization)
    tenant_id = validate_tenant_id(tenant_id)
    require_tenant_owner(user, tenant_id)
    require_permission(user, "documents:write")

    policy = validate_access_policy(
        access_scope,
        parse_csv_values(allowed_roles),
        parse_csv_values(allowed_users),
    )
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    tenant_dir = DATA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[str] = []

    try:
        for uploaded_file in files:
            filename = validate_pdf_filename(uploaded_file.filename or "")
            content = await uploaded_file.read(MAX_UPLOAD_BYTES + 1)
            if not content:
                raise HTTPException(status_code=400, detail=f"Empty file: {filename}")
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
                )
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=400,
                    detail=f"File does not have a valid PDF signature: {filename}",
                )
            (tenant_dir / filename).write_bytes(content)
            saved_files.append(filename)

        documents = build_documents(
            data_dir=DATA_DIR,
            tenant_id=tenant_id,
            selected_files=saved_files,
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
            user=user,
            document_ids=document_ids,
            sources=saved_files,
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
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Document indexing failed. Check backend logs for the request ID.",
        ) from exc


@app.post("/ingest")
def ingest(
    request: IngestRequest,
    x_demo_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user, authorization)
    tenant_id = validate_tenant_id(request.tenant_id)
    require_tenant_owner(user, tenant_id)
    require_permission(user, "documents:write")

    policy = validate_access_policy(
        request.access_scope,
        request.allowed_roles,
        request.allowed_users,
    )

    try:
        ingest_data_dir = DATA_DIR
        if (
            not (DATA_DIR / tenant_id).exists()
            and (REPO_DATA_DIR / tenant_id).exists()
        ):
            ingest_data_dir = REPO_DATA_DIR

        documents = build_documents(
            data_dir=ingest_data_dir,
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
        document_ids = sorted(
            {item["metadata"]["document_id"] for item in documents}
        )
        chunks_indexed = store.replace_documents(
            documents=documents,
            tenant_id=tenant_id,
            user=user,
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
    except Exception as exc:
        logger.exception("Ingestion failed for tenant_id=%s", tenant_id)
        raise HTTPException(
            status_code=500,
            detail="Ingestion failed. Check backend logs for the request ID.",
        ) from exc


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_demo_user: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = get_current_user(x_demo_user, authorization)
    require_permission(user, "documents:read")
    require_permission(user, "compliance:analyze")
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    try:
        return agent.run(question=question, user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Analysis failed.") from exc
