import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from backend.rag.long_term_memory import LongTermMemory

async def test_long_memory():
    user_id = 0
    ltm = LongTermMemory(user_id)
    # 测试获取记忆（当前为空）
    mem = ltm.get_relevant_memory("测试查询")
    print(f"当前记忆内容: '{mem}'")
    # 测试保存记忆
    print("长期记忆模块初始化成功")


if __name__ == "__main__":
    asyncio.run(test_long_memory())