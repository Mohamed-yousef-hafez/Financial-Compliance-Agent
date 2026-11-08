
import json
import math
import os
from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb
from google import genai
from google.genai import types

from app.core.config import SUPABASE_DB_URL
from app.core.security import (
    UserContext,
    access_flag_key,
    authorized_documents,
)

EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-001",
)
EMBEDDING_DIMENSIONS = 768
TABLE_NAME = "public.compliance_chunks"


class SupabaseVectorStore:
    """Postgres/pgvector store using Supabase and Gemini embeddings."""

    def __init__(self):
        if not SUPABASE_DB_URL:
            raise RuntimeError("SUPABASE_DB_URL is not configured")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        self.database_url = SUPABASE_DB_URL
        self.embedding_client = genai.Client(api_key=api_key)

    @contextmanager
    def _tenant_connection(self, tenant_id: str):
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        with psycopg.connect(
            self.database_url,
            autocommit=False,
            connect_timeout=10,
            prepare_threshold=None,
        ) as conn:
            conn.execute("SET search_path TO public, extensions")

            conn.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (tenant_id,),
            )

            yield conn

    @staticmethod
    def _validate_user_tenant(user: UserContext, tenant_id: str):
        if user.tenant_id != tenant_id:
            raise PermissionError("Cross-tenant database access denied")

    @staticmethod
    def _validate_documents(documents, tenant_id):
        for item in documents:
            metadata = item.get("metadata")

            if not isinstance(metadata, dict):
                raise ValueError("Document metadata must be a dictionary")

            if metadata.get("tenant_id") != tenant_id:
                raise PermissionError(
                    "Document tenant_id does not match the requested tenant"
                )

            if not item.get("text"):
                raise ValueError("Document text cannot be empty")

    @staticmethod
    def _build_id(metadata):
        return (
            f"{metadata['tenant_id']}:"
            f"{metadata['document_id']}:"
            f"{metadata['page']}:"
            f"{metadata['chunk_id']}"
        )

    @staticmethod
    def _vector_literal(values):
        return "[" + ",".join(
            f"{float(value):.9f}" for value in values
        ) + "]"

    def _embed_texts(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        vectors = []
        batch_size = 16

        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]

            result = self.embedding_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                    task_type=task_type,
                ),
            )

            batch_vectors = getattr(result, "embeddings", None) or []

            if len(batch_vectors) != len(batch):
                raise RuntimeError(
                    "Gemini returned an unexpected number of embeddings"
                )

            for embedding in batch_vectors:
                values = [float(value) for value in embedding.values]
                norm = math.sqrt(sum(value * value for value in values))

                if not norm:
                    raise RuntimeError(
                        "Gemini returned an empty embedding vector"
                    )

                vectors.append([value / norm for value in values])

        return vectors

    @staticmethod
    def _prepare_rows(documents, embeddings):
        unique = {}

        for item, embedding in zip(documents, embeddings):
            metadata = item["metadata"]
            row_id = SupabaseVectorStore._build_id(metadata)
            unique[row_id] = (item, embedding)

        rows = []

        for row_id, (item, embedding) in unique.items():
            metadata = item["metadata"]

            rows.append(
                (
                    row_id,
                    metadata["tenant_id"],
                    metadata["document_id"],
                    metadata["source"],
                    item["text"],
                    Jsonb(metadata),
                    SupabaseVectorStore._vector_literal(embedding),
                )
            )

        return rows

    @staticmethod
    def _insert_rows(conn, rows):
        if not rows:
            return 0

        sql = f"""
            INSERT INTO {TABLE_NAME}
                (
                    id,
                    tenant_id,
                    document_id,
                    source,
                    content,
                    metadata,
                    embedding,
                    updated_at
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector, NOW())
            ON CONFLICT (id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                document_id = EXCLUDED.document_id,
                source = EXCLUDED.source,
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """

        conn.cursor().executemany(sql, rows)
        return len(rows)

    @staticmethod
    def _delete_rows(
        conn,
        tenant_id,
        document_ids=None,
        sources=None,
    ):
        conditions = ["tenant_id = %s"]
        params = [tenant_id]

        if document_ids:
            conditions.append("document_id = ANY(%s::text[])")
            params.append(list(document_ids))

        if sources:
            conditions.append("source = ANY(%s::text[])")
            params.append(list(sources))

        sql = (
            f"DELETE FROM {TABLE_NAME} WHERE "
            + " AND ".join(conditions)
        )

        conn.execute(sql, params)

    def delete_documents(
        self,
        tenant_id,
        user: UserContext,
        document_ids=None,
        sources=None,
    ):
        self._validate_user_tenant(user, tenant_id)

        with self._tenant_connection(tenant_id) as conn:
            self._delete_rows(
                conn,
                tenant_id,
                document_ids=document_ids,
                sources=sources,
            )

    def replace_documents(
        self,
        documents,
        tenant_id,
        user: UserContext,
        document_ids=None,
        sources=None,
    ):
        self._validate_user_tenant(user, tenant_id)

        if not documents:
            return 0

        self._validate_documents(documents, tenant_id)

        texts = [item["text"] for item in documents]

        embeddings = self._embed_texts(
            texts,
            "RETRIEVAL_DOCUMENT",
        )

        rows = self._prepare_rows(documents, embeddings)

        if not sources and not document_ids:
            raise ValueError(
                "document_ids or sources are required for replacement"
            )

        with self._tenant_connection(tenant_id) as conn:
            self._delete_rows(
                conn,
                tenant_id,
                document_ids=document_ids,
                sources=sources,
            )

            return self._insert_rows(conn, rows)

    def _security_where(self, user: UserContext):
        conditions = ["tenant_id = %s"]
        params = [user.tenant_id]

        if "admin" in user.roles:
            return " AND ".join(conditions), params

        access_conditions = [
            "COALESCE(metadata ->> 'access_scope', 'tenant') = 'tenant'"
        ]

        for role in user.roles:
            access_conditions.append("metadata ->> %s = 'true'")
            params.append(access_flag_key("access_role", role))

        access_conditions.append("metadata ->> %s = 'true'")
        params.append(access_flag_key("access_user", user.user_id))

        conditions.append(
            "(" + " OR ".join(access_conditions) + ")"
        )

        return " AND ".join(conditions), params

    def query(
        self,
        question,
        user: UserContext,
        top_k=8,
    ):
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        if int(top_k) < 1:
            raise ValueError("top_k must be greater than zero")

        query_embedding = self._embed_texts(
            [question],
            "RETRIEVAL_QUERY",
        )[0]

        query_vector = self._vector_literal(query_embedding)
        where_sql, where_params = self._security_where(user)

        sql = f"""
            SELECT
                content,
                metadata,
                1 - (embedding <=> %s::vector) AS similarity
            FROM {TABLE_NAME}
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """

        params = [
            query_vector,
            *where_params,
            query_vector,
            int(top_k),
        ]

        with self._tenant_connection(user.tenant_id) as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []

        for content, metadata, similarity in rows:
            if not isinstance(metadata, dict):
                metadata = json.loads(metadata)

            score = max(0.0, min(1.0, float(similarity)))

            results.append(
                {
                    "text": content,
                    "metadata": metadata,
                    "vector_score": score,
                }
            )

        return authorized_documents(user, results)
