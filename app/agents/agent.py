from app.core.config import RERANK_K
from app.core.risk import classify_risk
from app.core.security import (
    UserContext,
    authorize,
    is_prompt_injection,
)
from app.retrieval.reranker import rerank


class ComplianceAgent:
    def __init__(self, retriever, generator=None):
        self.retriever = retriever
        self.generator = generator

    def _get_generator(self):
        if self.generator is None:
            from app.generation.generator import GeminiGenerator
            self.generator = GeminiGenerator()
        return self.generator

    def run(self, question: str, user: UserContext):
        authorize(user, "compliance:analyze")

        if not question or not question.strip():
            raise ValueError("question is required")

        question = question.strip()
        decision_trace = [
            f"Authenticated user: {user.user_id}",
            f"Tenant isolated to: {user.tenant_id}",
            f"Roles: {', '.join(user.roles) or 'none'}",
        ]

        if is_prompt_injection(question):
            decision_trace.append("Prompt injection detected")
            return {
                "answer": (
                    "I cannot process this request because it contains "
                    "a prompt injection attempt."
                ),
                "risk": {
                    "level": "high",
                    "matched_terms": ["prompt injection"],
                },
                "sources": [],
                "requires_human_approval": True,
                "decision_trace": decision_trace,
            }

        decision_trace.append("Prompt-injection check passed before retrieval")

        risk = classify_risk(question)
        decision_trace.append(f"Risk classified as {risk['level']}")

        retrieved = self.retriever.search(
            question=question,
            user=user,
        )
        decision_trace.append(
            "Permission-aware retrieval completed "
            f"with {len(retrieved)} authorized evidence items"
        )

        ranked = rerank(question, retrieved, limit=RERANK_K)
        decision_trace.append(
            f"Reranked to {len(ranked)} authorized evidence items"
        )

        generator = self._get_generator()
        answer = generator.generate(question=question, evidence=ranked)
        decision_trace.append("Answer generated using authorized grounded evidence")

        sources = [
            {
                "source": item["metadata"]["source"],
                "page": item["metadata"]["page"],
                "score": round(item.get("rerank_score", 0.0), 4),
                "text": item["text"],
            }
            for item in ranked
        ]

        requires_human_approval = risk["level"] == "high"
        decision_trace.append(
            "Human approval required"
            if requires_human_approval
            else "No human approval required"
        )

        return {
            "answer": answer,
            "risk": risk,
            "sources": sources,
            "requires_human_approval": requires_human_approval,
            "decision_trace": decision_trace,
        }
