"""
    文件路径 配置
"""


import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


# 项目根目录
BASE_DIR = Path(__file__).parent.parent
# 显式加载 .env 文件
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    """全局配置（从 .env 和环境变量加载）"""

    # MySQL 配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "robotvacuum"
    DB_PASSWORD: str = "robotvacuum"
    DB_NAME: str = "robotvacuum"

    # 模型配置
    model_name: str = "qwen3:8b"
    model_name2: str = "glm4:9b"
    base_url: str = "http://localhost:11434"
    embedding_name: str = "bge-m3"
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # 分词参数
    chunk_size: int = 600
    chunk_overlap: int = 100
    separators: list = ["\n\n\n", "\n\n", "。", "！", "？", "\n", "；", "，", " ", ""]

    # 向量库配置
    collection_name: str = "agents"
    persist_directory_name: str = "rag/chroma_db"
    k: int = 3
    allowed_type: tuple = ("txt", "pdf")

    # 路径配置
    vector_store_path: str = "data"
    log_save_file: str = "backend/logs"
    md5_file_path: str = "md5.txt"

    # 长期记忆配置
    long_term_similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    long_term_max_memories: int = Field(default=200, gt=0)
    long_term_k_retrieval: int = Field(default=3, gt=0)
    long_term_memory_dir: str = "rag/long_term_memory"

    # 评估 & Prompts 路径
    evaluate_ques2query_path: str = "evaluate/ques2query_dataset.json"
    agent_prompts: str = "prompts/agent_prompt.txt"
    summarize_prompts: str = "prompts/rag_summarize_prompt.txt"
    repair_prompts: str = "prompts/rag_repair_prompt.txt"
    maintain_prompts: str = "prompts/rag_maintain_prompt.txt"
    guide_prompts: str = "prompts/rag_guide_prompt.txt"
    report_prompts: str = "prompts/report_prompt.txt"
    query_routing_prompts: str = "prompts/rag_query_routing.txt"
    query_rewriting_prompts: str = "prompts/rag_query_rewriting.txt"


    # RL 导航配置
    use_rl_navigation: bool = False
    rl_model_path: str = "./rl_models/pure/final_robot_policy.zip"
    rl_hybrid_mode: bool = False

    # 杂项
    get_greetings: list = []
    get_stopwards: list = ["吗", "啊", "哦", "哦哦", "哦哦哦"]

    class Config:
        case_sensitive = False
        extra = "ignore"



# 全局单例
settings = Settings()





if __name__ == "__main__":
    print("BASE_DIR:", BASE_DIR)
