import subprocess
import tempfile
import os
import pwd
import time
import resource
import shutil
import logging
from abc import ABC, abstractmethod
from typing import Optional, List
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import JudgeRequest, JudgeResponse, BatchJudgeRequest, BatchJudgeResponse

logger = logging.getLogger(__name__)

# judge 用户 uid/gid（Dockerfile 中创建）
try:
    _JUDGE_USER = pwd.getpwnam("judge")
    JUDGE_UID = _JUDGE_USER.pw_uid
    JUDGE_GID = _JUDGE_USER.pw_gid
except KeyError:
    # 本地开发时可能没有 judge 用户，fallback 到当前用户
    JUDGE_UID = os.getuid()
    JUDGE_GID = os.getgid()


def _make_preexec_fn(memory_limit_mb: int, use_rlimit_as: bool = True):
    """
    创建 preexec_fn，在子进程中设置资源限制。
    在 fork 后、exec 前执行，限制用户代码的资源使用。

    :param memory_limit_mb: 内存限制（MB）
    :param use_rlimit_as: 是否用 RLIMIT_AS 限制虚拟地址空间。
           C/C++/Python 适用；Java/Go/Node 的运行时会保留远超实际使用量的虚拟内存，
           设了 RLIMIT_AS 会直接崩溃，这些语言靠自身参数（-Xmx、--max-old-space-size）限制。
    """
    def preexec():
        # 切换到 judge 用户
        if os.getuid() == 0:
            os.setgid(JUDGE_GID)
            os.setuid(JUDGE_UID)

        # 内存限制（仅对 C/C++/Python 等原生进程有效）
        if use_rlimit_as and memory_limit_mb > 0:
            mem_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        # 限制子进程数（防止 fork 炸弹）
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))

        # 限制输出文件大小（32MB，防止写大文件）
        file_limit = 32 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))

        # 禁止创建 core dump
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return preexec


class BaseExecutor(ABC):
    """代码执行器基类"""

    @abstractmethod
    def get_file_extension(self) -> str:
        """获取源代码文件扩展名"""
        pass

    @abstractmethod
    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        """
        获取编译命令
        返回 None 表示解释型语言无需编译
        """
        pass

    @abstractmethod
    def get_run_cmd(self, work_dir: str, source_file: str, request: JudgeRequest) -> List[str]:
        """获取执行命令"""
        pass

    def get_run_memory_limit(self, request: JudgeRequest) -> int:
        """获取运行时内存限制（MB），子类可覆盖以调整"""
        return request.memory_limit

    def use_rlimit_as(self) -> bool:
        """是否使用 RLIMIT_AS 限制虚拟地址空间。
        Java/Go/Node 等 managed runtime 应覆盖为 False。"""
        return True

    def get_source_filename(self) -> str:
        """获取源代码文件名"""
        return f"main{self.get_file_extension()}"

    def before_compile(self, source_file: str, work_dir: str, request: JudgeRequest) -> Optional[str]:
        """编译前钩子，返回新的 source_file 路径（如需重命名）"""
        return None

    def execute(self, request: JudgeRequest) -> JudgeResponse:
        """执行代码并返回结果"""
        work_dir = None
        try:
            # 创建临时工作目录
            work_dir = tempfile.mkdtemp(prefix="judge_")

            # 写入源代码
            source_file = os.path.join(work_dir, self.get_source_filename())
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(request.code)

            # 编译前钩子（如 Java 需要重命名文件）
            new_source = self.before_compile(source_file, work_dir, request)
            if new_source:
                source_file = new_source

            # 设置临时目录权限，让 judge 用户可读写
            os.chmod(work_dir, 0o777)
            for root, dirs, files in os.walk(work_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o777)
                for f in files:
                    os.chmod(os.path.join(root, f), 0o666)

            # 编译（如需要，编译以 root 执行，运行以 judge 用户执行）
            compile_result = self._compile(source_file, work_dir, request)
            if compile_result is not None:
                return compile_result

            # 编译后确保产物可执行
            output_bin = os.path.join(work_dir, "main")
            if os.path.exists(output_bin):
                os.chmod(output_bin, 0o755)

            # 执行
            return self._run(work_dir, source_file, request)

        except Exception as e:
            logger.exception(f"Execute error: {e}")
            return JudgeResponse(
                success=False,
                error=f"System error: {str(e)}",
                status="SE"
            )
        finally:
            # 清理临时目录
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    # FC 函数超时 300s，留 10 秒余量给编译和响应序列化
    BATCH_TOTAL_TIMEOUT_SEC = 290

    def execute_batch(self, request: BatchJudgeRequest) -> BatchJudgeResponse:
        """批量执行：编译一次，跑 N 个测试用例"""
        work_dir = None
        total_start = time.time()
        try:
            work_dir = tempfile.mkdtemp(prefix="judge_")

            # 写入源代码
            source_file = os.path.join(work_dir, self.get_source_filename())
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(request.code)

            # 构造一个临时的 JudgeRequest 用于 before_compile 和 _compile
            tmp_req = JudgeRequest(
                code=request.code,
                language=request.language,
                time_limit=request.time_limit,
                memory_limit=request.memory_limit,
            )

            # 编译前钩子
            new_source = self.before_compile(source_file, work_dir, tmp_req)
            if new_source:
                source_file = new_source

            # 设置目录权限
            os.chmod(work_dir, 0o777)
            for root, dirs, files in os.walk(work_dir):
                for d in dirs:
                    os.chmod(os.path.join(root, d), 0o777)
                for f_name in files:
                    os.chmod(os.path.join(root, f_name), 0o666)

            # 记录编译前的原始文件列表（用于用例间清理）
            original_files = set()
            for root, dirs, files in os.walk(work_dir):
                for f_name in files:
                    original_files.add(os.path.join(root, f_name))

            # 编译（只编译一次）
            compile_result = self._compile(source_file, work_dir, tmp_req)
            if compile_result is not None:
                return BatchJudgeResponse(
                    success=False,
                    error=compile_result.error,
                    status="CE",
                    total_time=int((time.time() - total_start) * 1000),
                )

            # 编译后确保产物可执行，并更新原始文件列表
            output_bin = os.path.join(work_dir, "main")
            if os.path.exists(output_bin):
                os.chmod(output_bin, 0o755)
            for root, dirs, files in os.walk(work_dir):
                for f_name in files:
                    original_files.add(os.path.join(root, f_name))

            # 逐个跑测试用例
            results = []
            for i, test_case in enumerate(request.test_cases):
                # 检查总时间，确保剩余时间足够跑完当前用例
                elapsed_total = time.time() - total_start
                remaining = self.BATCH_TOTAL_TIMEOUT_SEC - elapsed_total
                case_timeout_sec = request.time_limit / 1000.0
                if remaining < case_timeout_sec:
                    logger.warning(f"Batch timeout at case {i}/{len(request.test_cases)}, "
                                   f"elapsed={elapsed_total:.1f}s, remaining={remaining:.1f}s < case_limit={case_timeout_sec}s")
                    break

                case_req = JudgeRequest(
                    code=request.code,
                    language=request.language,
                    input=test_case.input,
                    time_limit=request.time_limit,
                    memory_limit=request.memory_limit,
                )
                result = self._run(work_dir, source_file, case_req)
                results.append(result)

                # 遇到非 OK 结果时停止
                if request.stop_on_first_fail and result.status != "OK":
                    break

                # 清理用户代码可能创建的临时文件（防止跨用例数据泄露）
                self._cleanup_user_files(work_dir, original_files)

            return BatchJudgeResponse(
                success=True,
                results=results,
                total_time=int((time.time() - total_start) * 1000),
            )

        except Exception as e:
            logger.exception(f"Batch execute error: {e}")
            return BatchJudgeResponse(
                success=False,
                error=f"System error: {str(e)}",
                status="SE",
                total_time=int((time.time() - total_start) * 1000),
            )
        finally:
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def _cleanup_user_files(work_dir: str, original_files: set):
        """清理用户代码在运行期间创建的文件，保留编译产物"""
        try:
            for root, dirs, files in os.walk(work_dir):
                for f_name in files:
                    fpath = os.path.join(root, f_name)
                    if fpath not in original_files:
                        os.remove(fpath)
        except Exception:
            pass

    def _compile(self, source_file: str, work_dir: str, request: JudgeRequest) -> Optional[JudgeResponse]:
        """编译代码，返回 None 表示编译成功或无需编译"""
        output_file = os.path.join(work_dir, "main")
        compile_cmd = self.get_compile_cmd(source_file, output_file)

        if compile_cmd is None:
            return None  # 解释型语言无需编译

        try:
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                timeout=30,  # 编译超时30秒
                cwd=work_dir
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='replace')
                return JudgeResponse(
                    success=False,
                    error=error_msg[:2000],
                    exit_code=result.returncode,
                    status="CE"
                )

            return None  # 编译成功

        except subprocess.TimeoutExpired:
            return JudgeResponse(
                success=False,
                error="Compilation timeout",
                status="CE"
            )

    def _run(self, work_dir: str, source_file: str, request: JudgeRequest) -> JudgeResponse:
        """以 judge 用户执行代码，带资源限制"""
        run_cmd = self.get_run_cmd(work_dir, source_file, request)
        timeout_sec = request.time_limit / 1000.0
        mem_limit = self.get_run_memory_limit(request)

        # 清除 RUSAGE_CHILDREN 累计值：fork 一个空子进程来"重置"基线
        # （getrusage 返回的是所有已回收子进程的累计峰值，无法直接重置）
        try:
            baseline = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        except Exception:
            baseline = 0

        # 构造干净的环境变量，移除敏感信息（防止用户代码读 /proc/self/environ）
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": "/home/judge",
            "LANG": "en_US.UTF-8",
            "JAVA_HOME": os.environ.get("JAVA_HOME", ""),
            "GOPATH": os.environ.get("GOPATH", ""),
        }
        # 过滤掉空值
        clean_env = {k: v for k, v in clean_env.items() if v}

        start_time = time.time()
        process = None

        try:
            process = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work_dir,
                env=clean_env,
                preexec_fn=_make_preexec_fn(mem_limit, self.use_rlimit_as()),
            )

            stdin_data = request.input.encode('utf-8') if request.input else None
            stdout_bytes, stderr_bytes = process.communicate(input=stdin_data, timeout=timeout_sec)

            elapsed_ms = int((time.time() - start_time) * 1000)

            # 采集子进程内存使用
            try:
                usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                memory_kb = usage.ru_maxrss
                if sys.platform == 'darwin':
                    memory_kb = memory_kb // 1024
                # 减去基线，得到本次进程的近似值（仍可能偏高，但比累计值好）
                memory_kb = max(0, memory_kb - (baseline if sys.platform != 'darwin' else baseline // 1024))
            except Exception:
                memory_kb = 0

            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')

            # 判断是否因内存超限被 kill（信号 9 或返回码 137）
            if process.returncode == -9 or process.returncode == 137:
                return JudgeResponse(
                    success=False,
                    error="Memory Limit Exceeded",
                    time_used=elapsed_ms,
                    memory_used=memory_kb,
                    status="MLE"
                )

            return JudgeResponse(
                success=True,
                output=stdout[:10000],
                error=stderr[:2000] if stderr else None,
                exit_code=process.returncode,
                time_used=elapsed_ms,
                memory_used=memory_kb,
                status="OK" if process.returncode == 0 else "RE"
            )

        except subprocess.TimeoutExpired:
            if process:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except Exception:
                    pass
            elapsed_ms = int((time.time() - start_time) * 1000)
            return JudgeResponse(
                success=False,
                error="Time Limit Exceeded",
                time_used=elapsed_ms,
                status="TLE"
            )
