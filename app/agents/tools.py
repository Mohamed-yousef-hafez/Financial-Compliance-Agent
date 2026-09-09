class ToolRegistry:
    def __init__(self, retriever):
        self.retriever = retriever

    def retrieve(
        self,
        question,
        tenant_id,
        top_k,
    ):
        return self.retriever.search(
            question,
            tenant_id,
            top_k,
        )