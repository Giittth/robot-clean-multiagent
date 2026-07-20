import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.vector.vector_store_new import vector_store


def test_vector_store():
    try:
        # 测试向量库集合是否存在
        collection = vector_store.vectorstore._collection
        count = collection.count()
        print(f"向量库连接成功，当前文档数: {count}")
    except Exception as e:
        print(f"向量库连接失败: {e}")

if __name__ == "__main__":
    test_vector_store()