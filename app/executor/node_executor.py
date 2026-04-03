from typing import Optional, List
from .base import BaseExecutor
from models import JudgeRequest


class NodeExecutor(BaseExecutor):
    """Node.js 执行器"""

    def get_file_extension(self) -> str:
        return ".js"

    def use_rlimit_as(self) -> bool:
        """V8 引擎保留大量虚拟地址空间，RLIMIT_AS 会导致崩溃"""
        return False

    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return None  # 解释型语言无需编译

    def get_run_cmd(self, work_dir: str, source_file: str, request: JudgeRequest) -> List[str]:
        return ["node", f"--max-old-space-size={request.memory_limit}", source_file]
