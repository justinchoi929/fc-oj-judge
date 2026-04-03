import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import JudgeRequest, JudgeResponse, BatchJudgeRequest, BatchJudgeResponse, Language
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

# Token 认证：通过环境变量配置共享密钥，后端调用时携带 Bearer Token
JUDGE_TOKEN = os.environ.get("JUDGE_TOKEN", "")

security = HTTPBearer(auto_error=False)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证 Bearer Token（后端 -> 沙箱的调用认证）"""
    if not JUDGE_TOKEN:
        return  # 未配置 Token 时跳过认证（开发环境）
    if not credentials or credentials.credentials != JUDGE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


# 创建 FastAPI 应用
app = FastAPI(
    title="OJ Judge Service",
    description="阿里云 FC 代码判题服务",
    version="1.0.0",
    docs_url=None,    # 生产环境关闭 Swagger
    redoc_url=None,
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


@app.post("/judge", response_model=JudgeResponse, dependencies=[Depends(verify_token)])
def judge(request: JudgeRequest) -> JudgeResponse:
    """执行代码判题。
    注意：使用 def（非 async def），FastAPI 会自动放到线程池执行，
    避免 subprocess 阻塞事件循环，支持真正的并发。
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
        logger.info(f"Judge result: status={result.status}, time={result.time_used}ms, mem={result.memory_used}KB")
        return result
    except Exception as e:
        logger.exception(f"Judge error: {e}")
        return JudgeResponse(
            success=False,
            error=f"Internal error: {str(e)}",
            status="SE"
        )


@app.post("/batch-judge", response_model=BatchJudgeResponse, dependencies=[Depends(verify_token)])
def batch_judge(request: BatchJudgeRequest) -> BatchJudgeResponse:
    """批量判题：编译一次，跑多个测试用例。
    注意：使用 def（非 async def），理由同上。
    """
    logger.info(f"Batch judge: language={request.language}, cases={len(request.test_cases)}, stop_on_fail={request.stop_on_first_fail}")

    executor = EXECUTORS.get(request.language)
    if not executor:
        return BatchJudgeResponse(
            success=False,
            error=f"Unsupported language: {request.language}",
            status="SE"
        )

    try:
        result = executor.execute_batch(request)
        passed = sum(1 for r in result.results if r.status == "OK")
        logger.info(f"Batch result: status={result.status}, passed={passed}/{len(result.results)}, total_time={result.total_time}ms")
        return result
    except Exception as e:
        logger.exception(f"Batch judge error: {e}")
        return BatchJudgeResponse(
            success=False,
            error=f"Internal error: {str(e)}",
            status="SE"
        )


@app.get("/health")
async def health():
    """健康检查（不需要认证）"""
    return {"status": "ok", "service": "oj-judge"}


@app.get("/languages", dependencies=[Depends(verify_token)])
async def languages():
    """获取支持的语言列表"""
    return {
        "languages": [
            {"id": "python", "name": "Python 3", "extension": ".py"},
            {"id": "java", "name": "Java 8", "extension": ".java"},
            {"id": "cpp", "name": "C++ 17", "extension": ".cpp"},
            {"id": "c", "name": "C 11", "extension": ".c"},
            {"id": "go", "name": "Go", "extension": ".go"},
            {"id": "nodejs", "name": "Node.js", "extension": ".js"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
