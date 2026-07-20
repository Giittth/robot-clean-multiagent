import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from backend.rag.rag_service import RagService


class TestRag:
    @staticmethod
    async def test_non_stream(user_id=0, kb_id=1, message="你好"):
        rag = RagService(user_id=user_id, kb_id=kb_id)
        try:
            result = await rag.generate_answer(query=message)
            print("=== 非流式回答 ===")
            print(f"Answer: {result['answer']}")
            print(f"Route: {result['route']}")
        except Exception as e:
            print(f"非流式错误: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    async def test_stream(user_id=0, kb_id=1, message="机器人使用完后怎么清理？"):
        rag = RagService(user_id=user_id, kb_id=kb_id)
        print("=== 流式回答 ===")
        full = ""
        try:
            async for chunk in rag.generate_answer_stream(query=message):
                print(chunk, end="", flush=True)
                full += chunk
            print("\n\n流式输出完成。")
        except Exception as e:
            print(f"\n流式错误: {e}")
            import traceback
            traceback.print_exc()

async def main():
    # 非流式测试
    # await TestRag.test_non_stream()
    # 流式测试
    await TestRag.test_stream()


if __name__ == "__main__":
    asyncio.run(main())