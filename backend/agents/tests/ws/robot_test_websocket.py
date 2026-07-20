"""
    测试机器人WebSocket连接的客户端
    建立WebSocket, 连接模拟机器人运动数据, 发送机器人状态数，持续运行
"""

import asyncio
import websockets
import json
import math

async def send_robot_data():
    # 连接前端的 WebSocket 地址
    uri = "ws://localhost:8000/ws/robot"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("测试脚本已连接后端，开始发送机器人位置...")

                t = 0
                while True:
                    # 让机器人画圈运动（平滑、好看）
                    x = 5 * math.cos(t)
                    y = 5 * math.sin(t)
                    theta = t + math.pi / 2

                    # 构造前端能识别的数据格式
                    data = {
                        "pose": {
                            "x": x,
                            "y": y,
                            "theta": theta
                        },
                        "sensor": {
                            "battery_voltage": 12.5,
                            "collision": False,
                            "laser": [2.0 for _ in range(360)]
                        },
                        "cleaned_area": 1.23,
                        "action": {
                            "linear": 0.5,
                            "angular": 0.2
                        },
                        "rag_advice": "沿墙壁清扫"
                    }

                    # 发送给后端 → 后端会转发给前端
                    await websocket.send(json.dumps(data))
                    await asyncio.sleep(0.05)  # 20 FPS 流畅运动
                    t += 0.02

        except Exception as e:
            print("连接断开，重试中...", e)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(send_robot_data())