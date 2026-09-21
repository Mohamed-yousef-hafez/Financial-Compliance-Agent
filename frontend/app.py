import os
import requests
import streamlit as st


st.set_page_config(
    page_title="Financial Compliance Agent",
    page_icon="💼",
    layout="wide",
)

API_URL = st.sidebar.text_input(
    "API URL",
    os.getenv("API_URL", "http://127.0.0.1:8000"),
).rstrip("/")

USER_OPTIONS = {
    "Admin — tenant_demo": "admin_demo",
    "Analyst — tenant_demo": "analyst_demo",
    "Manager — tenant_demo": "manager_demo",
    "Auditor — tenant_demo": "auditor_demo",
    "Analyst — tenant_b": "company_b_analyst",
}

selected_user_label = st.sidebar.selectbox(
    "Authenticated Demo User",
    list(USER_OPTIONS.keys()),
    index=0,
)
user_id = USER_OPTIONS[selected_user_label]

try:
    users_response = requests.get(f"{API_URL}/demo-users", timeout=10)
    if users_response.ok:
        users = {
            item["user_id"]: item
            for item in users_response.json().get("users", [])
        }
    else:
        users = {}
except requests.RequestException:
    users = {}

current_user = users.get(user_id, {})
tenant_id = current_user.get("tenant_id", "tenant_demo")
roles = current_user.get("roles", [])
permissions = current_user.get("permissions", [])

st.sidebar.caption(f"User: {user_id}")
st.sidebar.caption(f"Tenant: {tenant_id}")
st.sidebar.caption(f"Roles: {', '.join(roles) or 'none'}")

st.sidebar.divider()
st.sidebar.subheader("Document Management")

if "upload_result" not in st.session_state:
    st.session_state.upload_result = None

access_scope = st.sidebar.selectbox(
    "Document access",
    ["tenant", "roles", "users"],
    help="Controls which authenticated users can retrieve the uploaded document.",
)
allowed_roles = ""
allowed_users = ""

if access_scope == "roles":
    allowed_roles = st.sidebar.text_input(
        "Allowed roles",
        value="analyst,manager,auditor",
        help="Comma-separated role names.",
    )
elif access_scope == "users":
    allowed_users = st.sidebar.text_input(
        "Allowed users",
        value="analyst_demo",
        help="Comma-separated user IDs.",
    )

if st.sidebar.button("Index Included Demo Documents"):
    if "documents:write" not in permissions:
        st.sidebar.error("This user is not authorized to ingest documents.")
    else:
        try:
            response = requests.post(
                f"{API_URL}/ingest",
                json={
                    "tenant_id": tenant_id,
                    "access_scope": "tenant",
                },
                headers={"X-Demo-User": user_id},
                timeout=120,
            )
            if response.ok:
                st.sidebar.success("Included demo documents indexed.")
                st.sidebar.json(response.json())
            else:
                st.sidebar.error(f"Ingest failed: {response.text}")
        except requests.RequestException as exc:
            st.sidebar.error(f"API connection failed: {exc}")

uploaded_files = st.sidebar.file_uploader(
    "Upload PDF documents",
    type=["pdf"],
    accept_multiple_files=True,
)

if st.sidebar.button("Upload & Index"):
    if "documents:write" not in permissions:
        st.sidebar.error("This user is not authorized to upload documents.")
    elif not uploaded_files:
        st.sidebar.warning("Please upload at least one PDF.")
    else:
        files = [
            (
                "files",
                (file.name, file.getvalue(), "application/pdf"),
            )
            for file in uploaded_files
        ]
        try:
            response = requests.post(
                f"{API_URL}/upload",
                params={
                    "tenant_id": tenant_id,
                    "access_scope": access_scope,
                    "allowed_roles": allowed_roles,
                    "allowed_users": allowed_users,
                },
                headers={"X-Demo-User": user_id},
                files=files,
                timeout=120,
            )
            if response.ok:
                st.session_state.upload_result = response.json()
                st.sidebar.success("Documents uploaded successfully.")
            else:
                st.sidebar.error(f"Upload failed: {response.text}")
        except requests.RequestException as exc:
            st.sidebar.error(f"API connection failed: {exc}")

if st.session_state.upload_result:
    st.sidebar.json(st.session_state.upload_result)

if st.sidebar.button("Clear Tenant Documents"):
    try:
        response = requests.delete(
            f"{API_URL}/documents/{tenant_id}",
            headers={"X-Demo-User": user_id},
            timeout=60,
        )
        if response.ok:
            st.sidebar.success("Tenant vectors cleared.")
            st.sidebar.json(response.json())
        else:
            st.sidebar.error(f"Clear failed: {response.text}")
    except requests.RequestException as exc:
        st.sidebar.error(f"API connection failed: {exc}")

st.title("Financial Compliance Agent")
st.caption("Secure multi-tenant RAG with permission-aware retrieval")

st.subheader("Ask a Compliance Question")
question = st.text_area(
    "Question",
    placeholder="Example: What is the standard payment period?",
    height=120,
)

if st.button("Analyze", type="primary"):
    if "compliance:analyze" not in permissions:
        st.error("This user is not authorized to analyze compliance documents.")
    elif not question.strip():
        st.warning("Please enter a question.")
    else:
        try:
            response = requests.post(
                f"{API_URL}/chat",
                json={"question": question},
                headers={"X-Demo-User": user_id},
                timeout=120,
            )

            if not response.ok:
                st.error(response.text)
            else:
                result = response.json()
                st.subheader("Answer")
                st.write(result["answer"])

                st.subheader("Risk")
                risk = result["risk"]
                if risk["level"] == "high":
                    st.error("HIGH RISK — Human approval required")
                else:
                    st.success("LOW RISK")

                if risk["matched_terms"]:
                    st.write("Matched terms:", risk["matched_terms"])

                st.subheader("Authorized Evidence Used")
                sources = result.get("sources", [])
                if sources:
                    st.caption(
                        "Only evidence authorized for the authenticated user "
                        "is displayed here."
                    )
                    for index, source in enumerate(sources, start=1):
                        score_text = (
                            f"{float(source.get('score')):.4f}"
                            if source.get("score") is not None
                            else "N/A"
                        )
                        with st.expander(
                            f"{index}. {source.get('source', 'Unknown source')} "
                            f"— Page {source.get('page', 'N/A')} "
                            f"— Relevance: {score_text}"
                        ):
                            st.markdown("**Evidence text:**")
                            st.write(source.get("text", ""))
                else:
                    st.info("No supporting authorized evidence was found.")

                st.subheader("Decision Trace")
                for step in result.get("decision_trace", []):
                    st.write(f"✓ {step}")

        except requests.RequestException as exc:
            st.error(f"API connection failed: {exc}")
