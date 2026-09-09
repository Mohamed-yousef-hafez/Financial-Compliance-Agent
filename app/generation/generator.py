import os

from google import genai

from app.core.config import MIN_EVIDENCE_SCORE


class GeminiGenerator:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured"
            )

        self.client = genai.Client(
            api_key=api_key
        )

    def generate(self, question, evidence):
        if not evidence:
            return (
                "I cannot answer reliably because "
                "no supporting evidence was retrieved."
            )

        context_parts = []

        for item in evidence:
            if (
                item.get("rerank_score", 0)
                >= MIN_EVIDENCE_SCORE
            ):
                context_parts.append(
                    f"Source: {item['metadata']['source']}\n"
                    f"Page: {item['metadata']['page']}\n"
                    f"{item['text']}"
                )

        context = "\n\n".join(context_parts)

        if not context:
            return (
                "I cannot answer reliably because "
                "the retrieved evidence is insufficient."
            )

        prompt = f"""
You are a financial compliance assistant.

Answer the user's question using ONLY the provided evidence.

If the evidence does not support the answer, say:
"I cannot answer reliably from the available documents."

Do not invent policies, dates, amounts, approvals, or obligations.

User question:
{question}

Evidence:
{context}

Provide a concise answer and mention the relevant source.
"""

        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        return response.text.strip()