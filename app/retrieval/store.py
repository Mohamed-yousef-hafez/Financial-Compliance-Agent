import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
)

from app.core.config import CHROMA_DIR, EMBEDDING_MODEL


class ChromaStore:
    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        self.embedding_function = (
            SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
        )

        self.collection = self.client.get_or_create_collection(
            name="financial_compliance",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, documents):
        if not documents:
            return 0

        ids = []
        texts = []
        metadatas = []

        for item in documents:
            metadata = item["metadata"]

            document_id = metadata["document_id"]
            page = metadata["page"]
            chunk_id = metadata["chunk_id"]

            ids.append(
                f"{metadata['tenant_id']}:{document_id}:{page}:{chunk_id}"
            )

            texts.append(item["text"])
            metadatas.append(metadata)

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        return len(ids)

    def query(self, question, tenant_id, top_k=8):
        result = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            where={"tenant_id": tenant_id},
            include=["documents", "metadatas", "distances"],
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
                min(1.0, 1.0 - float(distance)),
            )

            rows.append(
                {
                    "text": text,
                    "metadata": metadata,
                    "vector_score": vector_score,
                }
            )

        return rows