"""
    文件方法
"""

import os
import hashlib
from langchain_community.document_loaders import PyPDFLoader, TextLoader

from backend.utils.logger_handler import logger
import backend.config as config


def get_project_root():
    """获取工程所在的根目录"""
    # 当前文件的绝对路径
    current_file = os.path.abspath(__file__)           # 绝对路径
    # 获取工程的根目录
    current_dir = os.path.dirname(current_file)
    # 获取根目录本身
    project_root = os.path.dirname(current_dir)
    return project_root

def get_abs_path(relative_path):
    """传入相对路径，返回绝对路径"""
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)

# 获取文件
def get_file(filepath, allowed_type):
    """筛选满足allowed_type格式的文件"""
    files = []
    if not os.path.isdir(filepath):
        logger.error(f"[内容获取]文件{filepath}不存在，请检查文件路径")
        return
    # 遍历文件夹内的文件
    for f in os.listdir(filepath):
        if f.endswith(allowed_type):
            files.append(os.path.join(filepath, f))
    return tuple(files)

# 将文件的内存转换为document对象
def file_loader(filepath):
    """将文件的内存转换为document对象"""
    # 判断文件是否存在
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在，请检查文件路径")
        return []
    # 判断是否为文件
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]文件{filepath}不是文件，请检查文件路径")
        return []

    try:
        if filepath.endswith(".txt"):
            return TextLoader(filepath, encoding="utf-8").load()

        elif filepath.endswith(".pdf"):
            return PyPDFLoader(filepath).load()

        else:
            logger.warning(f"[文件加载]不支持的文件类型：{filepath}")
            return []
    except Exception as e:
        logger.error(f"[文件加载]失败：{filepath}, 错误：{str(e)}")
        return []


# 保存md5
def save_md5(md5_text):
    """保存md5文件"""
    # os.makedirs(config.md5_file_path, exist_ok=True)
    with open(get_abs_path(config.md5_file_path), "a", encoding="utf-8") as f:
        f.write(md5_text + "\n")


# 将文件内容转换为md5文件
def get_md5(filepath):
    """"将文件内容转换为md5文件"""
    # 判断文件是否存在
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在，请检查文件路径")
        return
    # 判断是否为文件
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]文件{filepath}不是文件，请检查文件路径")
        return
    # 创建md5对象
    md5 = hashlib.md5()
    chunk_size = 4096
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
            md5_text = md5.hexdigest()
            return md5_text
    except Exception as e:
        logger.error(f"[md5计算]文件{filepath}计算md5失败，请检查文件路径")
        raise e

# 检查是否已经存在
def check_md5(md5_text):
    """检查md5.txt中是否已经存在md5_text"""
    if not os.path.exists(get_abs_path(config.md5_file_path)):
        open(get_abs_path(config.md5_file_path), "w", encoding="utf-8").close()
        return False
    with open(get_abs_path(config.md5_file_path), "r", encoding="utf-8") as f:
        for line in f.readlines():
            if md5_text == line.strip():
                return True
        return  False




if __name__ == "__main__":
    print(get_abs_path(config.vector_store_path))

    files = get_file(get_abs_path(config.vector_store_path), config.allowed_type)
    for f in files:
        md5_text = get_md5(f)
        document = file_loader(f)
        print(document[0])
        print(type(document[0]))



