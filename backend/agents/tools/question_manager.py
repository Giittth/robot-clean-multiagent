"""提问管理器：管理待用户回答的问题（文字输入版）"""
import asyncio
import uuid
from typing import Dict, Optional

class QuestionManager:
    """管理待用户回答的开放性问题"""

    def __init__(self):
        self._pending: Dict[str, asyncio.Event] = {}
        self._answers: Dict[str, str] = {}
        self._questions: Dict[str, str] = {}

    async def ask(self, question: str, timeout: float = 60.0) -> str:
        qid = uuid.uuid4().hex[:8]
        event = asyncio.Event()
        self._pending[qid] = event
        self._questions[qid] = question
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._answers.get(qid, "")
        except asyncio.TimeoutError:
            return ""
        finally:
            self._pending.pop(qid, None)
            self._answers.pop(qid, None)
            self._questions.pop(qid, None)

    def answer(self, qid: str, text: str) -> bool:
        if qid not in self._pending:
            return False
        self._answers[qid] = text
        self._pending[qid].set()
        return True

    def get_pending(self) -> list:
        return [{"id": qid, "question": q} for qid, q in self._questions.items()]


question_manager = QuestionManager()