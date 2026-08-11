from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class MemoryCategory(Enum):
    STRATEGY = "strategy"
    MARKET = "market"
    PRODUCT = "product"
    CREATIVE = "creative"
    UA = "ua"
    FINANCE = "finance"
    LESSON = "lesson"
    EXPERIMENT = "experiment"


@dataclass
class MemoryRecord:
    record_id: str
    category: MemoryCategory
    title: str
    content: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5
    source: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "category": self.category.value,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "importance": self.importance,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
        }


class CompanyMemoryDB:
    def __init__(self, db_path: str = "company_memory.db"):
        self.db_path = db_path
        self._records: Dict[str, MemoryRecord] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}

    def store(
        self,
        category: MemoryCategory,
        title: str,
        content: Dict[str, Any],
        tags: List[str] = None,
        importance: float = 0.5,
        source: str = "system",
    ) -> MemoryRecord:
        record_id = f"mem_{hash(title + str(datetime.now())) % 100000:05d}"

        record = MemoryRecord(
            record_id=record_id,
            category=category,
            title=title,
            content=content,
            tags=tags or [],
            importance=importance,
            source=source,
        )

        self._records[record_id] = record

        cat_key = category.value
        if cat_key not in self._category_index:
            self._category_index[cat_key] = []
        self._category_index[cat_key].append(record_id)

        for tag in record.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            self._tag_index[tag].append(record_id)

        return record

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        record = self._records.get(record_id)
        if record:
            record.access_count += 1
            record.last_accessed = datetime.now()
        return record

    def query(
        self,
        category: MemoryCategory = None,
        tags: List[str] = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> List[MemoryRecord]:
        results = list(self._records.values())

        if category:
            results = [r for r in results if r.category == category]

        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]

        results = [r for r in results if r.importance >= min_importance]
        results.sort(key=lambda r: (r.importance, r.created_at), reverse=True)

        return results[:limit]

    def get_by_tag(self, tag: str) -> List[MemoryRecord]:
        record_ids = self._tag_index.get(tag, [])
        return [self._records[rid] for rid in record_ids if rid in self._records]

    def get_by_category(self, category: MemoryCategory) -> List[MemoryRecord]:
        record_ids = self._category_index.get(category.value, [])
        return [self._records[rid] for rid in record_ids if rid in self._records]

    def update(self, record_id: str, updates: Dict[str, Any]) -> bool:
        record = self._records.get(record_id)
        if not record:
            return False

        if "title" in updates:
            record.title = updates["title"]
        if "content" in updates:
            record.content.update(updates["content"])
        if "tags" in updates:
            record.tags = updates["tags"]
        if "importance" in updates:
            record.importance = updates["importance"]

        record.updated_at = datetime.now()
        return True

    def delete(self, record_id: str) -> bool:
        if record_id not in self._records:
            return False

        record = self._records[record_id]

        if record.category.value in self._category_index:
            if record_id in self._category_index[record.category.value]:
                self._category_index[record.category.value].remove(record_id)

        for tag in record.tags:
            if tag in self._tag_index:
                if record_id in self._tag_index[tag]:
                    self._tag_index[tag].remove(record_id)

        del self._records[record_id]
        return True

    def search(self, keyword: str) -> List[MemoryRecord]:
        keyword_lower = keyword.lower()
        results = []
        for record in self._records.values():
            if (
                keyword_lower in record.title.lower()
                or any(keyword_lower in str(v).lower() for v in record.content.values())
                or any(keyword_lower in tag.lower() for tag in record.tags)
            ):
                results.append(record)
        results.sort(key=lambda r: r.importance, reverse=True)
        return results

    def get_stats(self) -> Dict[str, Any]:
        category_counts = {cat: len(ids) for cat, ids in self._category_index.items()}
        return {
            "total_records": len(self._records),
            "category_counts": category_counts,
            "total_tags": len(self._tag_index),
            "avg_importance": round(
                sum(r.importance for r in self._records.values()) / len(self._records), 2
            ) if self._records else 0,
        }
