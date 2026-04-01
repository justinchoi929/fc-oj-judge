from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Language(str, Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    GO = "go"
    NODEJS = "nodejs"


class JudgeRequest(BaseModel):
    """判题请求"""
    code: str                           # 源代码
    language: Language                  # 编程语言
    input: Optional[str] = ""           # 标准输入
    time_limit: int = 5000              # 时间限制（毫秒）
    memory_limit: int = 256             # 内存限制（MB）


class JudgeResponse(BaseModel):
    """判题响应"""
    success: bool                       # 是否成功
    output: Optional[str] = None        # 标准输出
    error: Optional[str] = None         # 错误信息
    exit_code: int = 0                  # 退出码
    time_used: int = 0                  # 实际用时（毫秒）
    memory_used: int = 0                # 实际内存（KB）
    status: str = "OK"                  # 状态：OK, CE, RE, TLE, MLE
