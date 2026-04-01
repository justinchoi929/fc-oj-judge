from typing import Optional, List
from .base import BaseExecutor


class PythonExecutor(BaseExecutor):
    """Python 3 执行器"""
    
    def get_file_extension(self) -> str:
        return ".py"
    
    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return None  # 解释型语言无需编译
    
    def get_run_cmd(self, work_dir: str, source_file: str) -> List[str]:
        return ["python3", source_file]
