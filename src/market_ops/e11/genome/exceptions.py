"""E11.1 Genome Exceptions — 创意基因组异常体系。"""

from __future__ import annotations


class GenomeError(Exception):
    """Genome 模块基础异常。"""
    pass


class GenomeNotFoundError(GenomeError):
    """请求的 Genome 不存在。"""

    def __init__(self, genome_id: str) -> None:
        self.genome_id = genome_id
        super().__init__(f"Genome not found: {genome_id!r}")


class GenomeDuplicateError(GenomeError):
    """尝试创建已存在的 Genome。"""

    def __init__(self, genome_id: str) -> None:
        self.genome_id = genome_id
        super().__init__(f"Genome already exists: {genome_id!r}")


class GenomeValidationError(GenomeError):
    """Genome 数据校验失败。"""

    def __init__(self, message: str, genome_id: str = "") -> None:
        self.genome_id = genome_id
        super().__init__(message)


class DNAMappingError(GenomeError):
    """DNA → Genome 转换失败。"""

    def __init__(self, message: str, source_id: str = "") -> None:
        self.source_id = source_id
        super().__init__(message)


class GenomeRepositoryError(GenomeError):
    """Genome 存储层错误。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)