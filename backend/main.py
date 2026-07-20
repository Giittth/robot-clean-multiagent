"""
FastAPI 搴旂敤鍏ュ彛锛氬彧璐熻矗鍒涘缓搴旂敤銆佹敞鍐岃矾鐢便€佹寕杞藉鍣ㄧ敓鍛藉懆鏈熴€?
"""

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.api import api_router
from backend.app.container import SystemContainer
from backend.app.lifecycle import startup as on_startup, shutdown as on_shutdown
import os


app = FastAPI(title="RAG + Robot System")

# CORS 閰嶇疆
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 娉ㄥ唽鑱氬悎璺敱锛堟墍鏈?API 缁熶竴鍓嶇紑 /api锛?
app.include_router(api_router)

# TTS 音频文件静态目录（供前端播放 MP3）
_tts_dir = os.path.join(os.path.dirname(__file__), "data", "tts_output")
os.makedirs(_tts_dir, exist_ok=True)
app.mount("/tts", StaticFiles(directory=_tts_dir), name="tts_audio")

# 鍏ㄥ眬瀹瑰櫒
container = SystemContainer()
app.state.container = container

# WebSocket 绔偣锛堢嫭绔嬩簬 HTTP 璺敱锛?
@app.websocket("/ws/robot")
async def websocket_robot(websocket: WebSocket):
    await container.ws_service.register_websocket(websocket)

# 鐢熷懡鍛ㄦ湡浜嬩欢
@app.on_event("startup")
async def startup():
    await on_startup(app)


@app.on_event("shutdown")
async def shutdown():
    await on_shutdown(app)

@app.get("/")
def root():
    return {"message": "Robot Agent System is running"}

@app.get("/health")
async def health_check():
    if container._running:
        return {"status": "healthy"}
    else:
        return {"status": "unhealthy", "detail": "Container not running"}, 503

