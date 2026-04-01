import os
from typing import Optional, List
from .base import BaseExecutor


class GoExecutor(BaseExecutor):
    """Go 执行器"""
    
    def get_file_extension(self) -> str:
        return ".go"
    
    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return [
            "go", "build",
            "-o", output_file,
            source_file
        ]
    
    def get_run_cmd(self, work_dir: str, source_file: str) -> List[str]:
        return [os.path.join(work_dir, "main")]
