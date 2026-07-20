"""
    稳定的WebSocket服务器模拟器，用于生成和发送机器人测试数据
    作为WebSocket服务器运行，模拟机器人运动数据，发送标准化数据包，稳定持续运行
"""

import asyncio
import math
import json
import time

async def send_state(websocket):
    start_time = time.time()
    radius = 3.0
    angular_speed = 0.8
    try:
        while True:
            now = time.monotonic() - start_time
            t = now
            x = radius * math.cos(t)
            y = radius * math.sin(t)
            theta = t + math.pi/2

            payload = {
                "pose": {"x": x, "y": y, "theta": theta},
                "sensor": {"battery_voltage": 12.0, "collision": False, "laser": [2.0]*360},
                "cleaned_area": 1.23,
                "action": {"linear": 0.5, "angular": angular_speed},
                "rag_advice": "匀速圆周运动"
            }
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(0.05)
    except Exception:
        pass

async def main():
    async with websockets.serve(send_state, "localhost", 8766):
        print("稳定模拟服务器已启动: ws://localhost:8766")
        print("每秒 20 帧，匀速圆周运动，数据平滑")
        await asyncio.Future()

if __name__ == "__main__":
    import websockets
    asyncio.run(main())