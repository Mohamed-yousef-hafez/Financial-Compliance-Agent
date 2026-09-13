import chromadb

from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
)

from app.core.config import CHROMA_DIR, EMBEDDING_MODEL


class ChromaStore:
    def __init__(self):
        CHROMA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        self.embedding_function = (
            SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
        )

        self.collection = (
            self.client.get_or_create_collection(
                name="financial_compliance",
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        )

    def _build_id(self, metadata):
        return (
            f"{metadata['tenant_id']}:"
            f"{metadata['document_id']}:"
            f"{metadata['page']}:"
            f"{metadata['chunk_id']}"
        )

    def delete_documents(
        self,
        tenant_id,
        document_ids=None,
        sources=None,
    ):
        where_conditions = []

        if tenant_id:
            where_conditions.append(
                {"tenant_id": tenant_id}
            )

        if document_ids:
            where_conditions.append(
                {"document_id": {"$in": document_ids}}
            )

        if sources:
            where_conditions.append(
                {"source": {"$in": sources}}
            )

        if not where_conditions:
            return

        if len(where_conditions) == 1:
            where = where_conditions[0]
        else:
            where = {"$and": where_conditions}

        self.collection.delete(where=where)

    def upsert(self, documents):
        if not documents:
            return 0

        ids = []
        texts = []
        metadatas = []

        for item in documents:
            metadata = item["metadata"]

            ids.append(
                self._build_id(metadata)
            )

            texts.append(item["text"])
            metadatas.append(metadata)

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        return len(ids)

    def replace_documents(
        self,
        documents,
        tenant_id,
        document_ids=None,
        sources=None,
    ):
        self.delete_documents(
            tenant_id=tenant_id,
            document_ids=document_ids,
            sources=sources,
        )

        return self.upsert(documents)

    def query(self, question, tenant_id, top_k=8):
        result = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            where={"tenant_id": tenant_id},
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        texts = documents[0]
        metadata_items = metadatas[0]
        distance_items = distances[0]

        rows = []

        for text, metadata, distance in zip(
            texts,
            metadata_items,
            distance_items,
        ):
            vector_score = max(
                0.0,
                min(
                    1.0,
                    1.0 - float(distance),
                ),
            )

            rows.append(
                {
                    "text": text,
                    "metadata": metadata,
                    "vector_score": vector_score,
                }
            )

        return rows