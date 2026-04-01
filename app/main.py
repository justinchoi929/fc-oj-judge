import logging
from fastapi import FastAPI, HTTPException
from models import JudgeRequest, JudgeResponse, Language
from executor import (
    PythonExecutor,
    JavaExecutor,
    CppExecutor,
    CExecutor,
    GoExecutor,
    NodeExecutor,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="OJ Judge Service",
    description="阿里云 FC 代码判题服务",
    version="1.0.0"
)

# 执行器映射
EXECUTORS = {
    Language.PYTHON: PythonExecutor(),
    Language.JAVA: JavaExecutor(),
    Language.CPP: CppExecutor(),
    Language.C: CExecutor(),
    Language.GO: GoExecutor(),
    Language.NODEJS: NodeExecutor(),
}


@app.post("/judge", response_model=JudgeResponse)
async def judge(request: JudgeRequest) -> JudgeResponse:
    """
    执行代码判题
    
    - **code**: 源代码
    - **language**: 编程语言 (python, java, cpp, c, go, nodejs)
    - **input**: 标准输入（可选）
    - **time_limit**: 时间限制，毫秒（默认5000）
    - **memory_limit**: 内存限制，MB（默认256）
    """
    logger.info(f"Judge request: language={request.language}, code_length={len(request.code)}")
    
    executor = EXECUTORS.get(request.language)
    if not executor:
        logger.error(f"Unsupported language: {request.language}")
        return JudgeResponse(
            success=False,
            error=f"Unsupported language: {request.language}",
            status="SE"
        )
    
    try:
        result = executor.execute(request)
        logger.info(f"Judge result: status={result.status}, time_used={result.time_used}ms")
        return result
    except Exception as e:
        logger.exception(f"Judge error: {e}")
        return JudgeResponse(
            success=False,
            error=f"Internal error: {str(e)}",
            status="SE"
        )


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "oj-judge"}


@app.get("/languages")
async def languages():
    """获取支持的语言列表"""
    return {
        "languages": [
            {"id": "python", "name": "Python 3", "extension": ".py"},
            {"id": "java", "name": "Java 11", "extension": ".java"},
            {"id": "cpp", "name": "C++ 17", "extension": ".cpp"},
            {"id": "c", "name": "C 11", "extension": ".c"},
            {"id": "go", "name": "Go", "extension": ".go"},
            {"id": "nodejs", "name": "Node.js", "extension": ".js"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
