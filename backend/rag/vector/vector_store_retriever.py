"""
    创建向量库对象
"""

import numpy as np
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.utils.file_handler import get_abs_path, get_file, file_loader, save_md5, get_md5, check_md5
from backend.config import settings
from backend.utils.logger_handler import logger



class VectorStore:
    def __init__(self):
        self.vectorstore = Chroma(
            collection_name=settings.collection_name,
            embedding_function=OllamaEmbeddings(model=settings.embedding_name, base_url=settings.base_url),
            persist_directory=settings.persist_directory_name
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=settings.separators,
            length_function=len
        )
    def get_retriever(self):
        return self.vectorstore.as_retriever(search_kwargs={"k": settings.k})

    # 获取向量库中的数据
    def get_data(self):
        return self.vectorstore.get()


    # 存入向量库
    def add_texts(self):
        """将数据存入到向量库中"""
        # 获取到文件夹内pdf，txt的文件

        files = get_file(get_abs_path(settings.vector_store_path), settings.allowed_type)

        print(get_abs_path(settings.vector_store_path))
        for f in files:
            # 获取md5文件
            print(f)
            md5_text = get_md5(f)

            # 检查md5文件是否已经存在
            if check_md5(md5_text):
                logger.info(f"[向量库加载]向量库已经存在，请勿重复添加")
                continue
            try:
                # 将文件内容转换为document对象
                documents = file_loader(f)

                if not documents:
                    logger.warining(f"[向量库加载]文件{f}为空，请检查文件内容")
                    continue
                split_document = self.splitter.split_documents(documents)
                if not split_document:
                    logger.warining(f"[向量库加载]文件{f}为空，请检查文件内容")
                    continue

                # 将内容存入向量库
                self.vectorstore.add_documents(split_document)

                # 保存md5
                save_md5(md5_text)
                logger.info(f"[向量库加载]文件{f}已添加到向量库")
            except Exception as e:
                logger.error(f"[向量库加载]文件{f}添加到向量库失败，请检查文件内容")
                raise e

vector_store = VectorStore()





if __name__ == "__main__":
    # vector_store = VectorStore()

    # vector_store.add_texts()
    # print(config.vector_store_path)
    # retriever = vector_store.get_retriever()
    # print(retriever)
    ...