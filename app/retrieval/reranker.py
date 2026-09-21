def rerank(question, results, limit=5):
    ranked = []

    for result in results:
        score = (
            0.8 * result["hybrid_score"]
            + 0.2 * result["lexical_score"]
        )

        updated = dict(result)
        updated["rerank_score"] = score

        ranked.append(updated)

    ranked.sort(
        key=lambda item: item["rerank_score"],
        reverse=True,
    )

    return ranked[:limit]