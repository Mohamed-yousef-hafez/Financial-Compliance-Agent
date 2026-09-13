from app.core.config import RERANK_K
from app.core.risk import classify_risk
from app.core.security import (
    is_prompt_injection,
    require_tenant,
)

from app.generation.generator import GeminiGenerator
from app.retrieval.reranker import rerank


class ComplianceAgent:
    def __init__(self, retriever, generator=None):
        self.retriever = retriever
        self.generator = generator

    def _get_generator(self):
        if self.generator is None:
            self.generator = GeminiGenerator()

        return self.generator

    def run(self, question, tenant_id):
        tenant_id = require_tenant(tenant_id)

        if not question or not question.strip():
            raise ValueError("question is required")

        question = question.strip()

        decision_trace = []

        if is_prompt_injection(question):
            decision_trace.append(
                "Prompt injection detected"
            )

            return {
                "answer": (
                    "I cannot process this request "
                    "because it contains a prompt injection attempt."
                ),
                "risk": {
                    "level": "high",
                    "matched_terms": [
                        "prompt injection"
                    ],
                },
                "sources": [],
                "requires_human_approval": True,
                "decision_trace": decision_trace,
            }

        decision_trace.append(
            "Security check passed"
        )

        risk = classify_risk(question)

        decision_trace.append(
            f"Risk classified as {risk['level']}"
        )

        retrieved = self.retriever.search(
            question=question,
            tenant_id=tenant_id,
        )

        decision_trace.append(
            f"Retrieved {len(retrieved)} documents"
        )

        ranked = rerank(
            question,
            retrieved,
            limit=RERANK_K,
        )

        decision_trace.append(
            f"Reranked to {len(ranked)} evidence items"
        )

        generator = self._get_generator()

        answer = generator.generate(
            question=question,
            evidence=ranked,
        )

        decision_trace.append(
            "Answer generated using grounded evidence"
        )

        sources = [
            {
                "source": item["metadata"]["source"],
                "page": item["metadata"]["page"],
                "score": round(
                    item.get("rerank_score", 0.0),
                    4,
                ),
                "text": item["text"],
            }
            for item in ranked
        ]

        requires_human_approval = (
            risk["level"] == "high"
        )

        if requires_human_approval:
            decision_trace.append(
                "Human approval required"
            )
        else:
            decision_trace.append(
                "No human approval required"
            )

        return {
            "answer": answer,
            "risk": risk,
            "sources": sources,
            "requires_human_approval": (
                requires_human_approval
            ),
            "decision_trace": decision_trace,
        }