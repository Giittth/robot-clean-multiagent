from typing import List, Dict
from backend.rag.vector.vector_store_new import vector_store


class VectorRetriever:
    @staticmethod
    def _build_filter(user_id: int, kb_id: int = None) -> dict[str, str]:
        filter_condition = {"user_id": str(user_id)}
        if kb_id is not None:
            filter_condition["kb_id"] = str(kb_id)
        return filter_condition

    @staticmethod
    def search(
        query: str,
        user_id: int,
        kb_id: int = None,
        top_k: int = 5
    ) -> List[Dict]:
        filter_condition = VectorRetriever._build_filter(user_id, kb_id)

        results = vector_store.vectorstore.similarity_search(
            query=query,
            k=top_k,
            filter=filter_condition
        )

        return [
            {
                "content": res.page_content,
                "metadata": res.metadata
            } for res in results
        ]

    @staticmethod
    def get_context(results: List[Dict]) -> str:
        return "\n\n".join([item["content"] for item in results])


retriever = VectorRetriever()