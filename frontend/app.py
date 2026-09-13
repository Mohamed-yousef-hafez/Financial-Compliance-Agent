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
    os.getenv(
        "API_URL",
        "http://127.0.0.1:8000",
    ),
)

tenant_id = st.sidebar.text_input(
    "Tenant ID",
    "tenant_demo",
)

st.sidebar.divider()

st.sidebar.subheader("Document Management")

if st.sidebar.button(
    "Clear Tenant Documents",
    type="secondary",
):
    try:
        clear_response = requests.delete(
            f"{API_URL}/documents",
            params={
                "tenant_id": tenant_id,
            },
            timeout=60,
        )

        if clear_response.ok:
            clear_data = clear_response.json()

            st.sidebar.success(
                f"Deleted {clear_data.get('files_deleted', 0)} file(s)."
            )

            st.sidebar.json(clear_data)

        else:
            st.sidebar.error(
                f"Clear failed: {clear_response.text}"
            )

    except requests.RequestException as exc:
        st.sidebar.error(
            f"API connection failed: {exc}"
        )

st.title("Financial Compliance Agent")

st.caption(
    "RAG-powered financial compliance analysis"
)


st.sidebar.divider()

st.sidebar.subheader("Document Ingestion")

uploaded_files = st.sidebar.file_uploader(
    "Upload PDF documents",
    type=["pdf"],
    accept_multiple_files=True,
)


if st.sidebar.button("Upload & Index"):
    if not tenant_id.strip():
        st.sidebar.warning(
            "Please enter a Tenant ID."
        )

    elif not uploaded_files:
        st.sidebar.warning(
            "Please upload at least one PDF."
        )

    else:
        files = [
            (
                "files",
                (
                    file.name,
                    file.getvalue(),
                    "application/pdf",
                ),
            )
            for file in uploaded_files
        ]

        try:
            response = requests.post(
                f"{API_URL}/upload",
                params={
                    "tenant_id": tenant_id,
                },
                files=files,
                timeout=120,
            )

            if response.ok:
                result = response.json()

                st.sidebar.success(
                    "Documents uploaded successfully."
                )

                st.sidebar.write(
                    f"Files uploaded: "
                    f"{len(result['files_uploaded'])}"
                )

                st.sidebar.write(
                    f"Chunks indexed: "
                    f"{result['chunks_indexed']}"
                )

            else:
                st.sidebar.error(
                    f"Upload failed: {response.text}"
                )

        except requests.RequestException as exc:
            st.sidebar.error(
                f"API connection failed: {exc}"
            )


st.subheader("Ask a Compliance Question")

question = st.text_area(
    "Question",
    placeholder=(
        "Example: What is the standard payment period?"
    ),
    height=120,
)


if st.button("Analyze", type="primary"):

    if not tenant_id.strip():
        st.warning(
            "Please enter a Tenant ID."
        )

    elif not question.strip():
        st.warning(
            "Please enter a question."
        )

    else:
        try:
            response = requests.post(
                f"{API_URL}/chat",
                json={
                    "tenant_id": tenant_id,
                    "question": question,
                },
                timeout=120,
            )

            if not response.ok:
                st.error(
                    response.text
                )

            else:
                result = response.json()

                st.subheader("Answer")

                st.write(
                    result["answer"]
                )

                st.subheader("Risk")

                risk = result["risk"]

                if risk["level"] == "high":
                    st.error(
                        "HIGH RISK — Human approval required"
                    )
                else:
                    st.success(
                        "LOW RISK"
                    )

                if risk["matched_terms"]:
                    st.write(
                        "Matched terms:",
                        risk["matched_terms"],
                    )

                st.subheader("Evidence Used")

                sources = result.get("sources", [])

                if sources:
                    st.caption(
                        "Evidence retrieved from the uploaded documents. "
                        "The relevance score is not a probability."
                    )

                    for index, source in enumerate(
                        sources,
                        start=1,
                    ):
                        source_name = source.get(
                            "source",
                            "Unknown source",
                        )

                        page = source.get(
                            "page",
                            "N/A",
                        )

                        score = source.get("score")

                        if score is not None:
                            score_text = f"{float(score):.4f}"
                        else:
                            score_text = "N/A"

                        with st.expander(
                            f"{index}. {source_name} "
                            f"— Page {page} "
                            f"— Relevance: {score_text}"
                        ):
                            evidence_text = source.get(
                                "text",
                                "Evidence text is not available.",
                            )

                            st.markdown("**Evidence text:**")
                            st.write(evidence_text)

                else:
                    st.info(
                        "No supporting evidence was found."
                    )

                    

                st.subheader("Decision Trace")

                decision_trace = result.get(
                    "decision_trace",
                    [],
                )

                if decision_trace:
                    for step in decision_trace:
                        st.write(f"✓ {step}")
                else:
                    st.info(
                        "No decision trace available."
                    )
                                    
                                

        except requests.RequestException as exc:
            st.error(
                f"API connection failed: {exc}"
            )