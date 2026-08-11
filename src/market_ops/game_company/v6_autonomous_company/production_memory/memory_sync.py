from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from .company_memory_db import CompanyMemoryDB, MemoryCategory, MemoryRecord
from .vector_memory import VectorMemory, VectorEntry
from .knowledge_graph_db import KnowledgeGraphDB, NodeType, EdgeType


class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncResult:
    sync_id: str
    status: SyncStatus
    records_synced: int = 0
    vectors_added: int = 0
    nodes_added: int = 0
    edges_added: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MemorySyncEngine:
    def __init__(
        self,
        memory_db: CompanyMemoryDB = None,
        vector_memory: VectorMemory = None,
        knowledge_graph: KnowledgeGraphDB = None,
    ):
        self.memory_db = memory_db or CompanyMemoryDB()
        self.vector_memory = vector_memory or VectorMemory()
        self.knowledge_graph = knowledge_graph or KnowledgeGraphDB()
        self._sync_history: List[SyncResult] = []

    def add_record_with_sync(
        self,
        category: MemoryCategory,
        title: str,
        content: Dict[str, Any],
        tags: List[str] = None,
        importance: float = 0.5,
        source: str = "system",
    ) -> SyncResult:
        sync_id = f"sync_{hash(title + str(datetime.now())) % 100000:05d}"
        result = SyncResult(
            sync_id=sync_id,
            status=SyncStatus.IN_PROGRESS,
            started_at=datetime.now(),
        )

        try:
            record = self.memory_db.store(
                category=category,
                title=title,
                content=content,
                tags=tags,
                importance=importance,
                source=source,
            )
            result.records_synced = 1

            vector_text = f"{title}\n{str(content)}"
            self.vector_memory.add(
                text=vector_text,
                metadata={"record_id": record.record_id, "category": category.value},
                category=category.value,
            )
            result.vectors_added = 1

            self._sync_to_graph(record)
            result.nodes_added = 1
            result.edges_added = 2

            result.status = SyncStatus.COMPLETED

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now()
        self._sync_history.append(result)
        return result

    def _sync_to_graph(self, record: MemoryRecord):
        category = record.category

        if category == MemoryCategory.PRODUCT:
            game_name = record.content.get("game_name", record.title)
            game_node = self.knowledge_graph.add_node(
                node_type=NodeType.GAME,
                name=game_name,
                properties=record.content,
            )

            genre = record.content.get("genre", "")
            if genre:
                genre_node = self.knowledge_graph.add_node(
                    node_type=NodeType.GENRE,
                    name=genre,
                )
                self.knowledge_graph.add_edge(
                    source_id=game_node.node_id,
                    target_id=genre_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                    weight=1.0,
                )

            audience = record.content.get("target_audience", "")
            if audience:
                audience_node = self.knowledge_graph.add_node(
                    node_type=NodeType.AUDIENCE,
                    name=audience,
                )
                self.knowledge_graph.add_edge(
                    source_id=game_node.node_id,
                    target_id=audience_node.node_id,
                    edge_type=EdgeType.TARGETS,
                    weight=1.0,
                )

        elif category == MemoryCategory.LESSON:
            insight_node = self.knowledge_graph.add_node(
                node_type=NodeType.INSIGHT,
                name=record.title,
                properties=record.content,
            )

    def batch_sync(self, records: List[Dict[str, Any]]) -> SyncResult:
        sync_id = f"sync_batch_{hash(str(datetime.now())) % 100000:05d}"
        result = SyncResult(
            sync_id=sync_id,
            status=SyncStatus.IN_PROGRESS,
            started_at=datetime.now(),
        )

        for record_data in records:
            try:
                cat = record_data.get("category", MemoryCategory.LESSON)
                if isinstance(cat, str):
                    cat = MemoryCategory(cat)

                sync_res = self.add_record_with_sync(
                    category=cat,
                    title=record_data.get("title", "Untitled"),
                    content=record_data.get("content", {}),
                    tags=record_data.get("tags", []),
                    importance=record_data.get("importance", 0.5),
                    source=record_data.get("source", "batch"),
                )

                result.records_synced += sync_res.records_synced
                result.vectors_added += sync_res.vectors_added
                result.nodes_added += sync_res.nodes_added
                result.edges_added += sync_res.edges_added
                result.errors.extend(sync_res.errors)

            except Exception as e:
                result.errors.append(str(e))

        if result.errors:
            result.status = SyncStatus.FAILED
        else:
            result.status = SyncStatus.COMPLETED

        result.completed_at = datetime.now()
        self._sync_history.append(result)
        return result

    def search_across_all(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        vector_results = self.vector_memory.search(query, top_k=top_k)
        keyword_results = self.memory_db.search(query)

        record_ids = set()
        for vr in vector_results:
            rid = vr.metadata.get("record_id")
            if rid:
                record_ids.add(rid)

        records = []
        for rid in list(record_ids)[:top_k]:
            rec = self.memory_db.get(rid)
            if rec:
                records.append(rec)

        for rec in keyword_results[:top_k]:
            if rec.record_id not in record_ids:
                records.append(rec)
                record_ids.add(rec.record_id)

        return {
            "records": [r.to_dict() for r in records[:top_k]],
            "vector_matches": len(vector_results),
            "keyword_matches": len(keyword_results),
            "total_unique": len(records),
        }

    def get_sync_history(self, limit: int = 20) -> List[SyncResult]:
        return self._sync_history[-limit:]

    def get_all_stats(self) -> Dict[str, Any]:
        return {
            "memory_db": self.memory_db.get_stats(),
            "vector_memory": self.vector_memory.get_stats(),
            "knowledge_graph": self.knowledge_graph.get_stats(),
            "sync_count": len(self._sync_history),
        }
