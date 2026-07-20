import uuid
from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

from backend.config import settings
from backend.models.db_model.knowledge import DocumentChunkDB
from backend.utils.logger_handler import logger
from backend.utils.file_handler import get_abs_path



class VectorStore:
    def __init__(self):
        self.embedding = OllamaEmbeddings(
            model=settings.embedding_name,
            base_url=settings.base_url
        )
        self.vectorstore = Chroma(
            collection_name=settings.collection_name,
            embedding_function=self.embedding,
            persist_directory=get_abs_path(settings.persist_directory_name)
        )

    def add_chunks(self, chunks: List[DocumentChunkDB]):
        if not chunks:
            logger.info("[向量库] 无切片需要入库")
            return

        texts = []
        metadatas = []
        ids = []

        for chunk in chunks:
            chunk_id = f"chunk_{uuid.uuid4()}"
            texts.append(chunk.content)

            # 全部转字符串，修复 filter 类型报错
            metadatas.append({
                "user_id": str(chunk.user_id),
                "kb_id": str(chunk.kb_id),
                "doc_id": str(chunk.doc_id)
            })
            ids.append(chunk_id)

        self.vectorstore.add_texts(
            texts=texts,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"[向量库] 成功入库 {len(chunks)} 条切片")

    def similarity_search(
        self,
        query: str,
        user_id: int,
        kb_id: int = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:

        # 转成字符串，满足 Chroma filter 类型要求
        filter_condition = {
            "user_id": str(user_id)
        }

        if kb_id is not None:
            filter_condition["kb_id"] = str(kb_id)

        # 检索
        results = self.vectorstore.similarity_search(
            query=query,
            k=top_k,
            filter=filter_condition
        )

        return [
            {
                "content": res.page_content,
                "metadata": res.metadata
            }
            for res in results
        ]

    def delete_by_doc_id(self, doc_id: int):
        try:
            self.vectorstore.delete(where={"doc_id": str(doc_id)})
            logger.info(f"[向量库] 已删除 doc_id={doc_id} 的向量")
        except Exception as e:
            logger.warning(f"[向量库] 删除 doc_id={doc_id} 失败: {str(e)}")

    def delete_by_kb_id(self, kb_id: int):
        try:
            self.vectorstore.delete(where={"kb_id": str(kb_id)})
            logger.info(f"[向量库] 已删除 kb_id={kb_id} 的向量")
        except Exception as e:
            logger.warning(f"[向量库] 删除 kb_id={kb_id} 失败: {str(e)}")


# 全局单例
vector_store = VectorStore()