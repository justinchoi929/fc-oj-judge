import os
from typing import Optional, List
from .base import BaseExecutor
from models import JudgeRequest


class CExecutor(BaseExecutor):
    """C 11 执行器"""

    def get_file_extension(self) -> str:
        return ".c"

    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return [
            "gcc",
            "-std=c11",
            "-O2",
            "-o", output_file,
            source_file,
            "-lm"
        ]

    def get_run_cmd(self, work_dir: str, source_file: str, request: JudgeRequest) -> List[str]:
        return [os.path.join(work_dir, "main")]
