from pydantic import BaseModel, validator
from typing import Optional, List
from enum import Enum

# 限制常量
MAX_CODE_LENGTH = 100 * 1024       # 100 KB
MAX_INPUT_LENGTH = 1 * 1024 * 1024  # 1 MB
MAX_TIME_LIMIT = 30000              # 30 秒
MAX_MEMORY_LIMIT = 512              # 512 MB


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

    @validator('code')
    def validate_code(cls, v):
        if len(v) > MAX_CODE_LENGTH:
            raise ValueError(f'Code too long: {len(v)} bytes, max {MAX_CODE_LENGTH}')
        return v

    @validator('input')
    def validate_input(cls, v):
        if v and len(v) > MAX_INPUT_LENGTH:
            raise ValueError(f'Input too long: {len(v)} bytes, max {MAX_INPUT_LENGTH}')
        return v

    @validator('time_limit')
    def validate_time_limit(cls, v):
        if v < 1000 or v > MAX_TIME_LIMIT:
            raise ValueError(f'time_limit must be between 1000 and {MAX_TIME_LIMIT}ms')
        return v

    @validator('memory_limit')
    def validate_memory_limit(cls, v):
        if v < 32 or v > MAX_MEMORY_LIMIT:
            raise ValueError(f'memory_limit must be between 32 and {MAX_MEMORY_LIMIT}MB')
        return v


class TestCase(BaseModel):
    """单个测试用例"""
    input: Optional[str] = ""           # 标准输入

    @validator('input')
    def validate_input(cls, v):
        if v and len(v) > MAX_INPUT_LENGTH:
            raise ValueError(f'Input too long: {len(v)} bytes, max {MAX_INPUT_LENGTH}')
        return v


class BatchJudgeRequest(BaseModel):
    """批量判题请求：编译一次，跑 N 个测试用例"""
    code: str                           # 源代码
    language: Language                  # 编程语言
    test_cases: List[TestCase]          # 测试用例列表
    time_limit: int = 5000              # 每个用例的时间限制（毫秒）
    memory_limit: int = 256             # 内存限制（MB）
    stop_on_first_fail: bool = True     # 遇到非 OK 结果时是否停止

    @validator('code')
    def validate_code(cls, v):
        if len(v) > MAX_CODE_LENGTH:
            raise ValueError(f'Code too long: {len(v)} bytes, max {MAX_CODE_LENGTH}')
        return v

    @validator('test_cases')
    def validate_test_cases(cls, v):
        if not v:
            raise ValueError('test_cases cannot be empty')
        if len(v) > 200:
            raise ValueError('test_cases max 200')
        return v

    @validator('time_limit')
    def validate_time_limit(cls, v):
        if v < 1000 or v > MAX_TIME_LIMIT:
            raise ValueError(f'time_limit must be between 1000 and {MAX_TIME_LIMIT}ms')
        return v

    @validator('memory_limit')
    def validate_memory_limit(cls, v):
        if v < 32 or v > MAX_MEMORY_LIMIT:
            raise ValueError(f'memory_limit must be between 32 and {MAX_MEMORY_LIMIT}MB')
        return v


class JudgeResponse(BaseModel):
    """判题响应（单个用例）"""
    success: bool                       # 是否成功
    output: Optional[str] = None        # 标准输出
    error: Optional[str] = None         # 错误信息
    exit_code: int = 0                  # 退出码
    time_used: int = 0                  # 实际用时（毫秒）
    memory_used: int = 0                # 实际内存（KB）
    status: str = "OK"                  # 状态：OK, CE, RE, TLE, MLE, SE


class BatchJudgeResponse(BaseModel):
    """批量判题响应"""
    success: bool                       # 整体是否成功（编译是否通过）
    error: Optional[str] = None         # 编译错误信息
    status: str = "OK"                  # 整体状态（CE 表示编译失败）
    results: List[JudgeResponse] = []   # 每个用例的运行结果
    total_time: int = 0                 # 总耗时（毫秒）
