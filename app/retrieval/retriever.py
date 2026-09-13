from app.core.config import TOP_K

from app.retrieval.store import ChromaStore
from app.retrieval.hybrid import (
    token_overlap,
    hybrid_score,
)


class Retriever:
    def __init__(self, store=None):
        self.store = store or ChromaStore()

    def search(
        self,
        question,
        tenant_id,
        top_k=TOP_K,
    ):
        results = self.store.query(
            question=question,
            tenant_id=tenant_id,
            top_k=top_k,
        )

        for result in results:
            lexical_score = token_overlap(
                question,
                result["text"],
            )

            result["lexical_score"] = lexical_score

            result["hybrid_score"] = hybrid_score(
                result["vector_score"],
                lexical_score,
            )

        return sorted(
            results,
            key=lambda item: item["hybrid_score"],
            reverse=True,
        )