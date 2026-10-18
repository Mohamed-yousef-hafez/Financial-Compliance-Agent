import json
import math
import os
from typing import Iterable

import psycopg
from psycopg.types.json import Jsonb
from google import genai
from google.genai import types

from app.core.config import SUPABASE_DB_URL
from app.core.security import UserContext, access_flag_key, authorized_documents

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = 768
TABLE_NAME = "public.compliance_chunks"


class SupabaseVectorStore:
    """Postgres/pgvector store using Supabase and Gemini-hosted embeddings."""

    def __init__(self):
        if not SUPABASE_DB_URL:
            raise RuntimeError("SUPABASE_DB_URL is not configured")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        self.database_url = SUPABASE_DB_URL
        self.embedding_client = genai.Client(api_key=api_key)
        self._ensure_table()

    def _connect(self):
        conn = psycopg.connect(
            self.database_url,
            autocommit=True,
            connect_timeout=10,
            prepare_threshold=None,
        )
        conn.execute("SET search_path TO public, extensions")
        return conn

    def _ensure_table(self):
        # Run sql/supabase_schema.sql in the Supabase SQL Editor first.
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    embedding extensions.vector({EMBEDDING_DIMENSIONS}) NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS compliance_chunks_tenant_idx "
                "ON public.compliance_chunks (tenant_id)"
            )

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
        return "[" + ",".join(f"{float(value):.9f}" for value in values) + "]"

    def _embed_texts(self, texts: list[str], task_type: str) -> list[list[float]]:
        vectors = []
        batch_size = 16
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
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
                raise RuntimeError("Gemini returned an unexpected number of embeddings")
            for embedding in batch_vectors:
                values = [float(value) for value in embedding.values]
                norm = math.sqrt(sum(value * value for value in values))
                if not norm:
                    raise RuntimeError("Gemini returned an empty embedding vector")
                # gemini-embedding-001 requires normalization when dimensions < 3072.
                vectors.append([value / norm for value in values])
        return vectors

    def delete_documents(self, tenant_id, document_ids=None, sources=None):
        if not tenant_id:
            return
        conditions = ["tenant_id = %s"]
        params: list[object] = [tenant_id]
        if document_ids:
            conditions.append("document_id = ANY(%s::text[])")
            params.append(list(document_ids))
        if sources:
            conditions.append("source = ANY(%s::text[])")
            params.append(list(sources))
        sql = f"DELETE FROM {TABLE_NAME} WHERE " + " AND ".join(conditions)
        with self._connect() as conn:
            conn.execute(sql, params)

    def upsert(self, documents):
        if not documents:
            return 0

        # Deduplicate IDs before sending them to Postgres.
        unique = {}
        for item in documents:
            metadata = item["metadata"]
            unique[self._build_id(metadata)] = item
        ids = list(unique.keys())
        items = [unique[key] for key in ids]
        texts = [item["text"] for item in items]
        embeddings = self._embed_texts(texts, "RETRIEVAL_DOCUMENT")

        sql = f"""
            INSERT INTO {TABLE_NAME}
                (id, tenant_id, document_id, source, content, metadata, embedding, updated_at)
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
        rows = []
        for row_id, item, embedding in zip(ids, items, embeddings):
            metadata = item["metadata"]
            rows.append(
                (
                    row_id,
                    metadata["tenant_id"],
                    metadata["document_id"],
                    metadata["source"],
                    item["text"],
                    Jsonb(metadata),
                    self._vector_literal(embedding),
                )
            )
        with self._connect() as conn:
            conn.cursor().executemany(sql, rows)
        return len(rows)

    def replace_documents(self, documents, tenant_id, document_ids=None, sources=None):
        # A changed file hash creates a new document_id. Delete by source first
        # so replacing a PDF with the same filename does not leave stale chunks.
        if sources:
            self.delete_documents(tenant_id=tenant_id, sources=sources)
        else:
            self.delete_documents(tenant_id=tenant_id, document_ids=document_ids)
        return self.upsert(documents)

    def _security_where(self, user: UserContext):
        conditions = ["tenant_id = %s"]
        params: list[object] = [user.tenant_id]
        if "admin" in user.roles:
            return " AND ".join(conditions), params

        access_conditions = ["COALESCE(metadata ->> 'access_scope', 'tenant') = 'tenant'"]
        for role in user.roles:
            access_conditions.append("metadata ->> %s = 'true'")
            params.append(access_flag_key("access_role", role))
        access_conditions.append("metadata ->> %s = 'true'")
        params.append(access_flag_key("access_user", user.user_id))
        conditions.append("(" + " OR ".join(access_conditions) + ")")
        return " AND ".join(conditions), params

    def query(self, question, user: UserContext, top_k=8):
        query_embedding = self._embed_texts([question], "RETRIEVAL_QUERY")[0]
        query_vector = self._vector_literal(query_embedding)
        where_sql, where_params = self._security_where(user)
        sql = f"""
            SELECT content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {TABLE_NAME}
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params = [query_vector, *where_params, query_vector, int(top_k)]
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []
        for content, metadata, similarity in rows:
            score = max(0.0, min(1.0, float(similarity)))
            results.append(
                {
                    "text": content,
                    "metadata": metadata if isinstance(metadata, dict) else json.loads(metadata),
                    "vector_score": score,
                }
            )
        # Defensive authorization check stays in place after database filtering.
        return authorized_documents(user, results)
