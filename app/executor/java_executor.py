import os
import re
from typing import Optional, List
from .base import BaseExecutor


class JavaExecutor(BaseExecutor):
    """Java 执行器"""
    
    def get_file_extension(self) -> str:
        return ".java"
    
    def get_source_filename(self) -> str:
        # Java 文件名需要与类名匹配，默认使用 Main.java
        return "Main.java"
    
    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return ["javac", "-encoding", "UTF-8", source_file]
    
    def get_run_cmd(self, work_dir: str, source_file: str) -> List[str]:
        # 从源文件中提取类名
        class_name = self._extract_class_name(source_file)
        return [
            "java",
            "-Xmx256m",
            "-Djava.security.manager",
            "-cp", work_dir,
            class_name
        ]
    
    def _extract_class_name(self, source_file: str) -> str:
        """从 Java 源代码中提取 public class 名称"""
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 查找 public class
            match = re.search(r'public\s+class\s+(\w+)', code)
            if match:
                return match.group(1)
            
            # 查找普通 class
            match = re.search(r'class\s+(\w+)', code)
            if match:
                return match.group(1)
                
        except Exception:
            pass
        
        return "Main"
