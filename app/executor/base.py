import subprocess
import tempfile
import os
import time
import shutil
from abc import ABC, abstractmethod
from typing import Optional, List
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import JudgeRequest, JudgeResponse


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
    def get_run_cmd(self, work_dir: str, source_file: str) -> List[str]:
        """获取执行命令"""
        pass
    
    def get_source_filename(self) -> str:
        """获取源代码文件名"""
        return f"main{self.get_file_extension()}"
    
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
            
            # 编译（如需要）
            compile_result = self._compile(source_file, work_dir, request)
            if compile_result is not None:
                return compile_result
            
            # 执行
            return self._run(work_dir, source_file, request)
            
        except Exception as e:
            return JudgeResponse(
                success=False,
                error=f"System error: {str(e)}",
                status="SE"
            )
        finally:
            # 清理临时目录
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
    
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
                    error=error_msg[:2000],  # 限制错误信息长度
                    exit_code=result.returncode,
                    status="CE"  # Compile Error
                )
            
            return None  # 编译成功
            
        except subprocess.TimeoutExpired:
            return JudgeResponse(
                success=False,
                error="Compilation timeout",
                status="CE"
            )
    
    def _run(self, work_dir: str, source_file: str, request: JudgeRequest) -> JudgeResponse:
        """执行代码"""
        run_cmd = self.get_run_cmd(work_dir, source_file)
        timeout_sec = request.time_limit / 1000.0
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                run_cmd,
                input=request.input.encode('utf-8') if request.input else None,
                capture_output=True,
                timeout=timeout_sec,
                cwd=work_dir
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            
            return JudgeResponse(
                success=True,
                output=stdout[:10000],  # 限制输出长度
                error=stderr[:2000] if stderr else None,
                exit_code=result.returncode,
                time_used=elapsed_ms,
                status="OK" if result.returncode == 0 else "RE"  # Runtime Error
            )
            
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return JudgeResponse(
                success=False,
                error="Time Limit Exceeded",
                time_used=elapsed_ms,
                status="TLE"
            )
