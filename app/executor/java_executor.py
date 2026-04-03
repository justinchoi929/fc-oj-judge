import os
import re
import logging
from typing import Optional, List
from .base import BaseExecutor
from models import JudgeRequest

logger = logging.getLogger(__name__)


class JavaExecutor(BaseExecutor):
    """Java 执行器"""

    def get_file_extension(self) -> str:
        return ".java"

    def get_source_filename(self) -> str:
        return "Main.java"

    def use_rlimit_as(self) -> bool:
        """JVM 保留大量虚拟地址空间，RLIMIT_AS 会导致启动崩溃"""
        return False

    def get_run_memory_limit(self, request: JudgeRequest) -> int:
        """Java 不使用 RLIMIT_AS，此值仅作记录"""
        return request.memory_limit

    def before_compile(self, source_file: str, work_dir: str, request: JudgeRequest) -> Optional[str]:
        """编译前根据 public class 名重命名源文件，解决文件名与类名不匹配的问题"""
        class_name = self._extract_class_name(source_file)
        expected_filename = f"{class_name}.java"
        current_filename = os.path.basename(source_file)

        if current_filename != expected_filename:
            new_path = os.path.join(work_dir, expected_filename)
            os.rename(source_file, new_path)
            logger.info(f"Renamed {current_filename} -> {expected_filename}")
            return new_path
        return None

    def get_compile_cmd(self, source_file: str, output_file: str) -> Optional[List[str]]:
        return ["javac", "-encoding", "UTF-8", source_file]

    def get_run_cmd(self, work_dir: str, source_file: str, request: JudgeRequest) -> List[str]:
        class_name = self._extract_class_name(source_file)
        return [
            "java",
            f"-Xmx{request.memory_limit}m",
            "-Djava.security.manager",
            "-cp", work_dir,
            class_name
        ]

    def _extract_class_name(self, source_file: str) -> str:
        """从 Java 源代码中提取 public class 名称"""
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                code = f.read()

            match = re.search(r'public\s+class\s+(\w+)', code)
            if match:
                return match.group(1)

            match = re.search(r'class\s+(\w+)', code)
            if match:
                return match.group(1)

        except Exception:
            pass

        return "Main"
