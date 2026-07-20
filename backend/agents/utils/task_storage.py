from typing import Optional, List, Dict
from backend.utils.logger_handler import logger


class TaskStorage:
    """内存任务存储，进程重启后自动清空"""

    def __init__(self, directory: str = None):
        # directory 参数保留，兼容原有调用方式，但不使用
        self._store: Dict[str, dict] = {}

    async def save(self, graph_id: str, data: dict):
        if not graph_id:
            logger.warning("TaskStorage: graph_id is empty, skip save")
            return
        self._store[graph_id] = data

    async def load(self, graph_id: str) -> Optional[dict]:
        return self._store.get(graph_id)

    async def list_pending(self) -> List[str]:
        return list(self._store.keys())

    async def delete(self, graph_id: str):
        self._store.pop(graph_id, None)