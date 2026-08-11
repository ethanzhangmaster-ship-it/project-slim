from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class MemoryType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PATTERN = "pattern"
    INSIGHT = "insight"
    RULE = "rule"


class MemoryStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


@dataclass
class MemoryEntry:
    entry_id: str
    memory_type: MemoryType
    category: str
    title: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    usage_count: int = 0
    success_rate: float = 0.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "memory_type": self.memory_type.value,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "status": self.status.value,
            "tags": self.tags,
            "related_entries": self.related_entries,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


@dataclass
class MemoryQuery:
    query_id: str
    filters: Dict[str, Any] = field(default_factory=dict)
    results: List[str] = field(default_factory=list)
    executed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "filters": self.filters,
            "results": self.results,
            "executed_at": self.executed_at.isoformat(),
        }


class GrowthMemory:
    def __init__(self):
        self._entries: Dict[str, MemoryEntry] = {}
        self._queries: List[MemoryQuery] = []
        self._categories: Dict[str, List[str]] = {}
        self._tags: Dict[str, List[str]] = {}
        self._index: Dict[str, List[str]] = {}

    def store(
        self,
        memory_type: MemoryType,
        category: str,
        title: str,
        content: str = "",
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
        confidence: float = 0.8
    ) -> MemoryEntry:
        entry_id = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        entry = MemoryEntry(
            entry_id=entry_id,
            memory_type=memory_type,
            category=category,
            title=title,
            content=content,
            metadata=metadata or {},
            confidence=confidence,
            tags=tags or [],
        )
        self._entries[entry_id] = entry
        self._update_indices(entry)
        return entry

    def _update_indices(self, entry: MemoryEntry):
        if entry.category not in self._categories:
            self._categories[entry.category] = []
        self._categories[entry.category].append(entry.entry_id)

        for tag in entry.tags:
            if tag not in self._tags:
                self._tags[tag] = []
            self._tags[tag].append(entry.entry_id)

        for word in entry.title.lower().split():
            if word not in self._index:
                self._index[word] = []
            if entry.entry_id not in self._index[word]:
                self._index[word].append(entry.entry_id)

    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._entries.get(entry_id)
        if entry:
            entry.usage_count += 1
            entry.last_used_at = datetime.now()
        return entry

    def search(
        self,
        memory_type: MemoryType = None,
        category: str = None,
        tags: List[str] = None,
        min_confidence: float = 0.0,
        keywords: List[str] = None
    ) -> List[MemoryEntry]:
        results = list(self._entries.values())

        if memory_type:
            results = [e for e in results if e.memory_type == memory_type]

        if category:
            results = [e for e in results if e.category == category]

        if tags:
            for tag in tags:
                results = [e for e in results if tag in e.tags]

        if min_confidence > 0:
            results = [e for e in results if e.confidence >= min_confidence]

        if keywords:
            for keyword in keywords:
                matching_ids = set(self._index.get(keyword.lower(), []))
                results = [e for e in results if e.entry_id in matching_ids]

        query_id = f"qry_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        query = MemoryQuery(
            query_id=query_id,
            filters={
                "memory_type": memory_type.value if memory_type else None,
                "category": category,
                "tags": tags,
                "min_confidence": min_confidence,
                "keywords": keywords,
            },
            results=[e.entry_id for e in results],
        )
        self._queries.append(query)

        return sorted(results, key=lambda e: e.confidence, reverse=True)

    def update_entry(
        self,
        entry_id: str,
        content: str = None,
        metadata: Dict[str, Any] = None,
        confidence: float = None,
        tags: List[str] = None
    ) -> Optional[MemoryEntry]:
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        if content is not None:
            entry.content = content
        if metadata is not None:
            entry.metadata.update(metadata)
        if confidence is not None:
            entry.confidence = confidence
        if tags is not None:
            entry.tags = tags

        return entry

    def archive(self, entry_id: str) -> Optional[MemoryEntry]:
        entry = self._entries.get(entry_id)
        if entry:
            entry.status = MemoryStatus.ARCHIVED
        return entry

    def get_successes(self, category: str = None) -> List[MemoryEntry]:
        return self.search(memory_type=MemoryType.SUCCESS, category=category)

    def get_failures(self, category: str = None) -> List[MemoryEntry]:
        return self.search(memory_type=MemoryType.FAILURE, category=category)

    def get_patterns(self) -> List[MemoryEntry]:
        return self.search(memory_type=MemoryType.PATTERN)

    def get_insights(self) -> List[MemoryEntry]:
        return self.search(memory_type=MemoryType.INSIGHT)

    def get_rules(self) -> List[MemoryEntry]:
        return self.search(memory_type=MemoryType.RULE)

    def get_categories(self) -> List[str]:
        return list(self._categories.keys())

    def get_tags(self) -> List[str]:
        return list(self._tags.keys())

    def get_entry_count(self, memory_type: MemoryType = None) -> int:
        if memory_type:
            return sum(1 for e in self._entries.values() if e.memory_type == memory_type)
        return len(self._entries)

    def get_query_history(self) -> List[MemoryQuery]:
        return list(self._queries)

    def get_stats(self) -> Dict[str, Any]:
        entries = list(self._entries.values())
        return {
            "total_entries": len(entries),
            "entries_by_type": {
                t.value: sum(1 for e in entries if e.memory_type == t)
                for t in MemoryType
            },
            "entries_by_status": {
                s.value: sum(1 for e in entries if e.status == s)
                for s in MemoryStatus
            },
            "total_categories": len(self._categories),
            "total_tags": len(self._tags),
            "total_queries": len(self._queries),
            "average_confidence": sum(e.confidence for e in entries) / len(entries) if entries else 0,
        }