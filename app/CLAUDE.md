[根目录](../CLAUDE.md) > **app**

# app -- FastAPI 应用模块

> 最后更新: 2026-04-02 17:53:27

## 模块职责

FastAPI 应用的全部业务代码, 包含 HTTP 路由、请求/响应模型定义、以及 6 种编程语言的代码执行器。负责接收代码提交、编译运行、资源限制、结果返回。

## 入口与启动

- **入口文件**: `main.py`
- **启动方式**: `python main.py` (内嵌 `uvicorn.run`, 监听 `0.0.0.0:9000`)
- **Dockerfile CMD**: `["python", "main.py"]`

## 对外接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/judge` | 单次代码执行, 返回 output/status/time_used/memory_used |
| POST | `/batch-judge` | 批量执行 (编译一次, 跑 N 个测试用例, 支持 stop_on_first_fail) |
| GET | `/health` | 健康检查 (无需认证) |
| GET | `/languages` | 返回支持的语言列表 |

认证: 除 `/health` 外, 所有接口需要 `Authorization: Bearer <JUDGE_TOKEN>` 头。

## 关键依赖与配置

**Python 依赖** (`requirements.txt`):
- fastapi==0.104.1
- uvicorn==0.24.0
- pydantic==2.5.2

**环境变量**:
- `JUDGE_TOKEN`: API 认证令牌, 未配置时跳过认证 (开发模式)
- `JAVA_HOME`, `GOPATH`, `PATH`: 编译器路径

## 数据模型

定义在 `models.py`:

| 模型 | 用途 |
|------|------|
| `Language` (Enum) | 支持的语言标识: python/java/cpp/c/go/nodejs |
| `JudgeRequest` | 单次执行请求: code, language, input, time_limit, memory_limit |
| `TestCase` | 批量模式的单个测试用例: input |
| `BatchJudgeRequest` | 批量执行请求: code, language, test_cases[], time_limit, memory_limit, stop_on_first_fail |
| `JudgeResponse` | 单次执行响应: success, output, error, exit_code, time_used, memory_used, status |
| `BatchJudgeResponse` | 批量执行响应: success, error, status, results[], total_time |

**校验约束**: code <= 100KB, input <= 1MB, time_limit 1000~30000ms, memory_limit 32~512MB, test_cases 最多 200 个。

## 执行器架构

采用**模板方法模式**, `BaseExecutor` 定义编译-运行流程, 子类只需实现:

| 抽象方法 | 说明 |
|---------|------|
| `get_file_extension()` | 源文件扩展名 |
| `get_compile_cmd(source, output)` | 编译命令 (返回 None 表示解释型语言) |
| `get_run_cmd(work_dir, source, request)` | 运行命令 |

可选覆盖: `use_rlimit_as()`, `get_run_memory_limit()`, `before_compile()`, `get_source_filename()`

**执行器列表**:

| 执行器 | 语言 | 编译型 | RLIMIT_AS | 特殊处理 |
|--------|------|--------|-----------|---------|
| PythonExecutor | Python 3 | 否 | 是 | -- |
| JavaExecutor | Java 8 | 是 | 否 | before_compile 重命名文件匹配 public class; -Xmx 堆限制; SecurityManager |
| CppExecutor | C++ 17 | 是 | 是 | g++ -std=c++17 -O2 |
| CExecutor | C 11 | 是 | 是 | gcc -std=c11 -O2 |
| GoExecutor | Go | 是 | 否 | Go 运行时虚拟内存大, 靠 FC 容器兜底 |
| NodeExecutor | Node.js | 否 | 否 | --max-old-space-size 堆限制 |

## 测试与质量

- 无自动化测试 (无 pytest/unittest 配置)
- 手工测试通过根目录 `test.html` 进行
- 无 linter/formatter 配置文件

## 常见问题 (FAQ)

**Q: 为什么 FastAPI handler 用 `def` 而不是 `async def`?**
A: `def` 路由会被 FastAPI 自动放到线程池执行, 避免 `subprocess.Popen` 阻塞事件循环, 实现真正的并发。

**Q: 如何扩展新语言?**
A: 新建 `executor/xxx_executor.py`, 继承 `BaseExecutor`, 实现 3 个抽象方法, 在 `main.py` 的 `EXECUTORS` 中注册, Dockerfile 中安装编译器。如果是 managed runtime, 覆盖 `use_rlimit_as()` 返回 `False`。

**Q: 批量模式如何防止超时?**
A: `execute_batch()` 在每个用例执行前检查剩余时间 (总上限 290s), 不足则提前终止。

## 相关文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `main.py` | 139 | FastAPI 入口, 路由, Token 认证 |
| `models.py` | 120 | Pydantic 请求/响应模型 |
| `executor/__init__.py` | 18 | 执行器导出 |
| `executor/base.py` | 394 | 基类: 编译/运行/资源限制/批量执行 |
| `executor/python_executor.py` | 17 | Python 执行器 |
| `executor/java_executor.py` | 72 | Java 执行器 (含文件重命名逻辑) |
| `executor/cpp_executor.py` | 25 | C++ 执行器 |
| `executor/c_executor.py` | 25 | C 执行器 |
| `executor/go_executor.py` | 26 | Go 执行器 |
| `executor/node_executor.py` | 21 | Node.js 执行器 |

## 变更记录 (Changelog)

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-04-02 | 初始化 | 首次生成模块文档 |
