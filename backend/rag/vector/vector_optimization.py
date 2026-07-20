"""
    优化向量库检索
"""

import jieba
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from typing import List

from backend.rag.vector.vector_store_new import vector_store
from backend.utils.logger_handler import logger


# BM25 最大文档数（超过则跳过关键词检索）
BM25_MAX_DOCS = 2000

class VectorOptimization:
    def __init__(self):
        self.vector_store = vector_store.vectorstore

    def get_user_documents(self, user_id: int, kb_id: int = None) -> List[Document]:
        """按用户权限获取文档（核心：隔离数据）"""
        conditions = [{"user_id": str(user_id)}]
        if kb_id is not None:
            conditions.append({"kb_id": str(kb_id)})

        where_filter = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        data = self.vector_store.get(where=where_filter)
        documents = []

        for i, content in enumerate(data["documents"]):
            if not content:
                continue
            metadata = data["metadatas"][i]
            documents.append(Document(page_content=content, metadata=metadata))

        return documents

    def hybrid_search(
        self,
        query: str,
        user_id: int,
        kb_id: int = None,
        top_k: int = 5
    ) -> List[Document]:
        """混合检索：Vector + BM25 + RRF重排，若文档数超过阈值则只用向量检索"""
        user_docs = self.get_user_documents(user_id, kb_id)
        if not user_docs:
            return []

        # 如果文档数量超过阈值，只做向量检索（避免内存爆炸）
        if len(user_docs) > BM25_MAX_DOCS:
            logger.info(f"文档数 {len(user_docs)} > {BM25_MAX_DOCS}，跳过 BM25，仅使用向量检索")
            filter_condition = {"user_id": str(user_id)}
            if kb_id:
                filter_condition["kb_id"] = str(kb_id)
            vector_docs = self.vector_store.similarity_search(
                query, k=top_k, filter=filter_condition
            )
            return vector_docs

        # 正常混合检索
        bm25_retriever = BM25Retriever.from_documents(
            user_docs,
            preprocess_func=lambda text: jieba.lcut(text.strip()),
            k=5
        )
        filter_condition = {"user_id": str(user_id)}
        if kb_id:
            filter_condition["kb_id"] = str(kb_id)
        vector_docs = self.vector_store.similarity_search(
            query, k=5, filter=filter_condition
        )

        # BM25 检索
        bm25_docs = bm25_retriever.invoke(query)
        # RRF 重排
        reranked = self._rrf_rerank(vector_docs, bm25_docs)
        return reranked[:top_k]


    @staticmethod
    def _rrf_rerank(vector_docs: List[Document], bm25_docs: List[Document], k: int = 60):
        doc_map = {}
        score_map = {}

        # 向量检索评分
        for rank, doc in enumerate(vector_docs):
            doc_key = hash(doc.page_content)
            doc_map[doc_key] = doc
            score_map[doc_key] = score_map.get(doc_key, 0) + 1.0 / (k + rank)

        # BM25 检索评分
        for rank, doc in enumerate(bm25_docs):
            doc_key = hash(doc.page_content)
            doc_map[doc_key] = doc
            score_map[doc_key] = score_map.get(doc_key, 0) + 1.0 / (k + rank)

        # 按分数排序
        sorted_items = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        final_docs = []

        for key, score in sorted_items:
            doc = doc_map[key]
            doc.metadata["rrf_score"] = round(score, 4)
            final_docs.append(doc)

        logger.info(f"[RRF重排] 向量:{len(vector_docs)} | BM25:{len(bm25_docs)} | 重排:{len(final_docs)}")
        return final_docs


# 全局单例，直接使用
vector_opt = VectorOptimization()



if __name__ == "__main__":
    # vector_store_optimization = VectorStoreOptimization()
    # retriever = vector_store_optimization.hybrid_retriever()
    ...



