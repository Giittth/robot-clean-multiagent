"""
FastAPI 应用生命周期管理：startup / shutdown 事件处理。

职责：
    - 启动时初始化数据库表并启动 SystemContainer（所有 Agent、服务）
    - 关闭时优雅停止 SystemContainer
"""

from backend.db.database import init_db_tables


async def startup(app):
    """应用启动：建表 → 启动容器（Agent / 服务 / 调度器）"""
    try:
        init_db_tables()
        print("数据库初始化完成")
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        raise

    container = app.state.container
    await container.start()


async def shutdown(app):
    """应用关闭：优雅停止容器"""
    container = app.state.container
    await container.stop()