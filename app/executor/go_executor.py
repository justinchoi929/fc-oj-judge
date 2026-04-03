import os
from typing import Optional, List
from .base import BaseExecutor
from models import JudgeRequest


class GoExecutor(BaseExecutor):
    """Go 执行器"""

    def get_file_extension(self) -> str:
        return ".go"

    def use_rlimit_as(self) -> bool:
        """Go 运行时保留数 GB 虚拟地址空间给 GC，RLIMIT_AS 会直接崩溃"""
        return False

    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return [
            "go", "build",
            "-o", output_file,
            source_file
        ]

    def get_run_cmd(self, work_dir: str, source_file: str, request: JudgeRequest) -> List[str]:
        return [os.path.join(work_dir, "main")]
