"""
    加载提示词
"""

from backend.config import settings
from backend.utils.logger_handler import logger
from backend.utils.file_handler import get_abs_path


# 加载agent提示词
def load_agent_prompts():
    try:
        prompt_path = get_abs_path(settings.agent_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到agent提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词agent文件")
        raise e

# 加载总结提示词
def load_summarize_prompts():
    try:
        prompt_path = get_abs_path(settings.summarize_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到总结提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词总结文件")
        raise e

# 加载故障修理提示词
def load_repair_prompts():
    try:
        prompt_path = get_abs_path(settings.repair_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到故障修理提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词故障修理文件")
        raise e

# 加载维护保养提示词
def load_maintain_prompts():
    try:
        prompt_path = get_abs_path(settings.maintain_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到维护保养提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词维护保养文件")
        raise e

# 加载选购指南提示词
def load_guide_prompts():
    try:
        prompt_path = get_abs_path(settings.guide_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到选购指南提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词选购指南文件")
        raise e

# 加载报告提示词
def load_report_prompts():
    try:
        prompt_path = get_abs_path(settings.report_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到报告提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词报告文件")
        raise e

# 加载查询路由提示词
def load_query_routing_prompts():
    try:
        prompt_path = get_abs_path(settings.query_routing_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到查询路由提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词查询路由文件")
        raise e

# 加载查询重写提示词
def load_query_rewriting_prompts():
    try:
        prompt_path = get_abs_path(settings.query_rewriting_prompts)
    except KeyError as e:
        logger.error(f"[提示词加载]未找到查询重写提示词路径，请检查配置文件")
        raise e
    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[提示词加载]加载失败，请检查提示词查询重写文件")
        raise e


# 调用函数
agent_prompts = load_agent_prompts()
summarize_prompts = load_summarize_prompts()
repair_prompts = load_repair_prompts()
maintain_prompts = load_maintain_prompts()
guide_prompts = load_guide_prompts()
report_prompts = load_report_prompts()
query_routing_prompts = load_query_routing_prompts()
query_rewriting_prompts = load_query_rewriting_prompts()

if __name__ == "__main__":
    print(agent_prompts)
    # print(load_summarize_prompts())
    # print(load_report_prompts())


