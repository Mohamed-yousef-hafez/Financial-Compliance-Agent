def recall_at_k(
    retrieved_ids,
    relevant_ids,
    k,
):
    retrieved = set(
        retrieved_ids[:k]
    )

    relevant = set(
        relevant_ids
    )

    if not relevant:
        return 0.0

    return len(
        retrieved & relevant
    ) / len(relevant)