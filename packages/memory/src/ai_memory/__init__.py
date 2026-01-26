"""
AI Memory Package - Memory system for AI Infrastructure.

This package provides the 3-tier PAI memory system:
- HOT: Redis for real-time task traces
- WARM: Qdrant for searchable learnings
- COLD: File archive for historical data

Also includes:
- KnowledgeFederation: Cross-project knowledge sharing (Improvement 5)
- SkillLibrary: Hierarchical skill patterns (Improvement 3)
"""

from .embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingService,
    get_embedding_service,
)
from .pai_memory import (
    KnowledgeFederation,
    Learning,
    LearningScope,
    MemoryTier,
    PAIMemory,
    PAIPhase,
)
from .qdrant import QdrantStore
from .skill_library import (
    Skill,
    SkillLevel,
    SkillLibrary,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Embeddings
    "EmbeddingService",
    "get_embedding_service",
    "EMBEDDING_DIMENSION",
    # Qdrant
    "QdrantStore",
    # PAI Memory
    "PAIMemory",
    "MemoryTier",
    "PAIPhase",
    "Learning",
    "LearningScope",
    # Knowledge Federation (Improvement 5)
    "KnowledgeFederation",
    # Skill Library (Improvement 3)
    "Skill",
    "SkillLevel",
    "SkillLibrary",
]
