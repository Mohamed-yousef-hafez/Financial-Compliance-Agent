# Financial Compliance Agent

Secure multi-tenant RAG system for financial compliance analysis.

## What was added

- Multi-tenant isolation enforced before retrieval.
- Server-side user identity for the local demo.
- Role-Based Access Control (RBAC).
- Document-level access scopes:
  - `tenant`: everyone in the same tenant can retrieve it.
  - `roles`: only selected roles can retrieve it.
  - `users`: only selected user IDs can retrieve it.
- Permission-aware Chroma retrieval.
- Post-retrieval authorization as defense in depth.
- Context protection: unauthorized chunks are removed before reranking/generation.
- Cross-tenant access protection.
- Server-side authorization for upload, ingest, clear, and chat.
- Security tests for tenant, role, user, and permission boundaries.
- Prompt-injection check remains before retrieval.
## Demo Video

Watch the Financial Compliance Agent interface demo:

[▶ Watch the Demo Video](https://github.com/user-attachments/assets/293082fa-6459-439f-8603-c0b5bf0538a0)
## Important security note

The included identity mechanism is a **local demo authentication layer**, not production authentication. Users are selected from a server-side demo registry and passed through the `X-Demo-User` header. For production, replace this with a verified JWT/OAuth2/SSO identity provider and a real user/role directory.

Never trust `tenant_id`, role, or permissions supplied directly by the client.

## Requirements

Python 3.12 is recommended.

## Windows local run

Open PowerShell in the project folder.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

The first run may download the BGE embedding model because the project uses ChromaDB with `BAAI/bge-small-en-v1.5`.

### 3. Configure Gemini

Copy `.env.example` to `.env` and add your Gemini API key:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.6-flash
```

You can change `GEMINI_MODEL` without changing the code.

### 4. Start the API

```powershell
python run.py
```

API docs:

`http://127.0.0.1:8000/docs`

### 5. Start Streamlit in a second terminal

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Open the URL shown by Streamlit, normally:

`http://localhost:8501`

## Demo users

The server contains these local demo identities:

| User | Tenant | Role | Main purpose |
|---|---|---|---|
| `admin_demo` | `tenant_demo` | admin | upload/manage/test all access |
| `analyst_demo` | `tenant_demo` | analyst | test restricted retrieval |
| `manager_demo` | `tenant_demo` | manager | test role-based access |
| `auditor_demo` | `tenant_demo` | auditor | test auditor access |
| `company_b_analyst` | `tenant_b` | analyst | test cross-tenant isolation |

The Streamlit sidebar lets you switch between these identities.

## Testing the security model

1. Select `admin_demo`.
2. Upload a PDF with `Document access = roles`.
3. Put `analyst` in `Allowed roles`.
4. Ask a question as `analyst_demo` — the document can be retrieved.
5. Switch to `manager_demo` — the same document is not retrieved unless `manager` is included.
6. Switch to `company_b_analyst` — documents belonging to `tenant_demo` remain inaccessible.
7. Upload with `Document access = users` and specify a user ID to test user-specific access.

## API security model

The request flow is:

```text
Authenticate user
        ↓
Resolve UserContext
        ↓
Authorize requested action
        ↓
Build server-side tenant/access filter
        ↓
Permission-aware vector retrieval
        ↓
Post-retrieval authorization check
        ↓
Rerank authorized evidence
        ↓
Build authorized context
        ↓
Generate grounded answer
```

### Chat

`POST /chat`

Send the authenticated identity in the header:

```text
X-Demo-User: analyst_demo
```

Body:

```json
{
  "question": "What is the standard payment period?"
}
```

The server derives tenant, roles, and permissions from the authenticated identity. The client cannot select another tenant by changing the JSON body.

### Upload

`POST /upload`

The authenticated user must have `documents:write` and can only upload to their own tenant.

Optional access controls:

```text
access_scope=tenant
access_scope=roles&allowed_roles=analyst,manager
access_scope=users&allowed_users=analyst_demo
```

### Ingest

`POST /ingest`

The same authorization rules apply.

### Clear tenant vectors

`DELETE /documents/{tenant_id}`

The authenticated user must belong to that tenant and have `documents:write`.

## Run tests

```powershell
pytest -q
```

The security-focused test suite covers:

- cross-tenant denial
- tenant-wide access
- role-based access
- user-specific access
- permission denial
- prompt injection
- agent behavior
- ingestion/chunking behavior

## Deployment

The project can still be deployed as separate FastAPI and Streamlit services. Configure the same environment variables in the deployment platform and replace the local demo authentication layer with the company's real identity provider before production use.
