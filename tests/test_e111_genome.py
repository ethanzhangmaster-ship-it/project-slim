"""E11.1 — Creative Genome Foundation Test.

5 AC covering:
  1. Genome Schema (CreativeGenome, Gene, GenomeLineage)
  2. DNA Mapping (winner DNA → CreativeGenome)
  3. Clone (parent → child, generation++)
  4. Lineage (ancestor chain tracking)
  5. Repository (save/load persistence)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from market_ops.e11 import (
    CreativeGenome,
    Gene,
    GenomeLineage,
    GENE_SLOTS,
    GenomeManager,
    DNAMapper,
    GenomeRepository,
    GenomeError,
    GenomeNotFoundError,
    GenomeDuplicateError,
    GenomeValidationError,
    DNAMappingError,
    GenomeRepositoryError,
)


# ═══════════════════════════════════════════════════════════
# AC1 — Genome Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_genome_schema_create():
    """AC1a: Create CreativeGenome with valid fields."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    fitness = {"ctr": 0.12, "cpi": 0.45, "roas_d7": 0.32}
    lineage = GenomeLineage(source="winner_001", created_by="dna_mapper")

    genome = CreativeGenome(
        genome_id="genome_001",
        parent_id=None,
        generation=0,
        genes=genes,
        fitness=fitness,
        lineage=lineage,
    )

    assert genome.genome_id == "genome_001"
    assert genome.parent_id is None
    assert genome.generation == 0
    assert genome.genes["hook"]["type"] == "rescue"
    assert genome.genes["hook"]["strength"] == 0.82
    assert genome.fitness["roas_d7"] == 0.32
    assert genome.lineage.source == "winner_001"
    assert genome.lineage.created_by == "dna_mapper"
    assert genome.lineage.created_at != ""


def test_ac1b_gene_schema():
    """AC1b: Gene dataclass creates correctly."""
    gene = Gene(name="hook", value="rescue", confidence=0.91, source="winner_analysis")

    assert gene.name == "hook"
    assert gene.value == "rescue"
    assert gene.confidence == 0.91
    assert gene.source == "winner_analysis"

    # to_dict / from_dict
    d = gene.to_dict()
    assert d["name"] == "hook"
    assert d["value"] == "rescue"

    gene2 = Gene.from_dict(d)
    assert gene2.name == gene.name
    assert gene2.value == gene.value


def test_ac1c_genome_serialization():
    """AC1c: CreativeGenome to_dict / from_dict roundtrip."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    genome = CreativeGenome(
        genome_id="genome_001",
        parent_id=None,
        generation=0,
        genes=genes,
        fitness={"ctr": 0.12},
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )

    d = genome.to_dict()
    assert d["genome_id"] == "genome_001"
    assert d["genes"]["hook"]["type"] == "rescue"
    assert d["lineage"]["source"] == "winner_001"

    restored = CreativeGenome.from_dict(d)
    assert restored.genome_id == genome.genome_id
    assert restored.genes["hook"]["type"] == "rescue"
    assert restored.fitness["ctr"] == 0.12


def test_ac1d_gene_slots():
    """AC1d: GENE_SLOTS defines 5 core dimensions."""
    assert "hook" in GENE_SLOTS
    assert "visual" in GENE_SLOTS
    assert "reward" in GENE_SLOTS
    assert "emotion" in GENE_SLOTS
    assert "gameplay" in GENE_SLOTS
    assert "type" in GENE_SLOTS["hook"]
    assert "strength" in GENE_SLOTS["hook"]
    assert "style" in GENE_SLOTS["visual"]
    assert "composition" in GENE_SLOTS["visual"]


# ═══════════════════════════════════════════════════════════
# AC2 — DNA Mapping
# ═══════════════════════════════════════════════════════════

def test_ac2_dna_to_genome():
    """AC2a: Winner DNA maps to CreativeGenome."""
    winner_dna = {
        "creative_id": "winner_001",
        "hook_type": "rescue",
        "first_3s_density": "high",
        "visual_style": "fantasy",
        "asset_type": "character_center",
        "reward": "unlock",
        "cta_strength": "strong",
        "emotion": "curiosity",
        "mechanism": "merge",
        "roi": 1.5,
        "ctr": 0.12,
        "spend": 5000.0,
        "label_confidence": 0.91,
    }

    mapper = DNAMapper()
    genome = mapper.map_winner_dna(winner_dna, source_id="winner_001")

    assert genome.genome_id == "genome_winner_001"
    assert genome.generation == 0
    assert genome.parent_id is None
    assert genome.genes["hook"]["type"] == "rescue"
    assert genome.genes["visual"]["style"] == "fantasy"
    assert genome.genes["reward"]["type"] == "unlock"
    assert genome.genes["emotion"]["primary"] == "curiosity"
    assert genome.genes["gameplay"]["mechanic"] == "merge"
    assert genome.fitness["roas_d7"] == 1.5
    assert genome.fitness["ctr"] == 0.12
    assert genome.lineage.source == "winner_001"
    assert genome.lineage.created_by == "dna_mapper"
    assert mapper.mapped_count == 1


def test_ac2b_dna_mapping_empty():
    """AC2b: Empty DNA raises DNAMappingError."""
    mapper = DNAMapper()
    try:
        mapper.map_winner_dna({}, source_id="empty")
        assert False, "Expected DNAMappingError"
    except DNAMappingError:
        pass


def test_ac2c_dna_mapping_batch():
    """AC2c: Batch mapping produces multiple genomes."""
    dna_list = [
        {"creative_id": "w_001", "hook_type": "rescue", "emotion": "curiosity", "roi": 1.5},
        {"creative_id": "w_002", "hook_type": "challenge", "emotion": "excitement", "roi": 2.0},
        {"creative_id": "w_003", "hook_type": "mystery", "emotion": "curiosity", "roi": 1.8},
    ]

    mapper = DNAMapper()
    genomes = mapper.map_batch(dna_list, prefix="genome")

    assert len(genomes) == 3
    assert genomes[0].genome_id == "genome_000"
    assert genomes[1].genome_id == "genome_001"
    assert genomes[2].genome_id == "genome_002"
    assert mapper.mapped_count == 3


# ═══════════════════════════════════════════════════════════
# AC3 — Clone
# ═══════════════════════════════════════════════════════════

def test_ac3_clone_genome():
    """AC3a: Clone produces child with parent tracking."""
    manager = GenomeManager()

    # 创建父代
    parent = manager.create_genome(
        genome_id="genome_001",
        genes={
            "hook": {"type": "rescue", "strength": 0.82},
            "visual": {"style": "fantasy", "composition": "character_center"},
            "reward": {"type": "unlock", "intensity": 0.75},
            "emotion": {"primary": "curiosity"},
            "gameplay": {"mechanic": "merge"},
        },
        fitness={"ctr": 0.12, "roas_d7": 0.32},
        source="winner_001",
    )

    assert parent.generation == 0
    assert parent.parent_id is None

    # 克隆
    child = manager.clone_genome("genome_001")

    assert child.genome_id == "genome_001_v1"
    assert child.parent_id == "genome_001"
    assert child.generation == 1
    assert child.genes["hook"]["type"] == "rescue"  # 继承基因
    assert child.genes["visual"]["style"] == "fantasy"
    assert child.lineage.source == "winner_001"
    assert child.lineage.created_by == "mutation_engine"
    assert manager.count() == 2


def test_ac3b_clone_preserves_genes():
    """AC3b: Clone preserves all genes from parent."""
    manager = GenomeManager()

    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    parent = manager.create_genome("genome_001", genes=genes, source="winner_001")

    child = manager.clone_genome("genome_001")

    # 修改子代基因不影响父代
    child.genes["hook"]["type"] = "mutated_hook"
    assert parent.genes["hook"]["type"] == "rescue"  # 父代未变
    assert child.genes["hook"]["type"] == "mutated_hook"  # 子代已变


def test_ac3c_clone_not_found():
    """AC3c: Clone non-existent genome raises GenomeNotFoundError."""
    manager = GenomeManager()
    try:
        manager.clone_genome("nonexistent")
        assert False, "Expected GenomeNotFoundError"
    except GenomeNotFoundError:
        pass


# ═══════════════════════════════════════════════════════════
# AC4 — Lineage
# ═══════════════════════════════════════════════════════════

def test_ac4_lineage_chain():
    """AC4a: Lineage chain tracks ancestor → descendant."""
    manager = GenomeManager()

    # 创建三代
    g0 = manager.create_genome("genome_001", genes={
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }, source="winner_001")

    g1 = manager.clone_genome("genome_001", new_id="genome_002")
    g2 = manager.clone_genome("genome_002", new_id="genome_003")

    # 谱系链
    chain = manager.get_lineage("genome_003")
    assert chain == ["genome_001", "genome_002", "genome_003"]

    # 祖先
    ancestor = manager.get_ancestor("genome_003")
    assert ancestor.genome_id == "genome_001"
    assert ancestor.lineage.source == "winner_001"


def test_ac4b_lineage_single():
    """AC4b: Single genome lineage returns itself."""
    manager = GenomeManager()
    manager.create_genome("genome_001", genes={
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }, source="winner_001")

    chain = manager.get_lineage("genome_001")
    assert chain == ["genome_001"]


def test_ac4c_update_genome():
    """AC4c: Update genome genes and fitness."""
    manager = GenomeManager()
    manager.create_genome("genome_001", genes={
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }, fitness={"ctr": 0.12}, source="winner_001")

    # 更新基因
    updated = manager.update_genome("genome_001", genes={
        "hook": {"type": "challenge", "strength": 0.90},
    })
    assert updated.genes["hook"]["type"] == "challenge"
    assert updated.genes["hook"]["strength"] == 0.90

    # 更新 fitness
    updated2 = manager.update_genome("genome_001", fitness={"roas_d7": 0.50})
    assert updated2.fitness["roas_d7"] == 0.50
    assert updated2.fitness["ctr"] == 0.12  # 原有字段保留


# ═══════════════════════════════════════════════════════════
# AC5 — Repository
# ═══════════════════════════════════════════════════════════

def test_ac5_repository_save_load():
    """AC5a: Save and load genome via file repository."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    genome = CreativeGenome(
        genome_id="genome_001",
        parent_id=None,
        generation=0,
        genes=genes,
        fitness={"ctr": 0.12, "roas_d7": 0.32},
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = GenomeRepository(storage_dir=tmpdir)

        # 保存
        path = repo.save(genome)
        assert Path(path).exists()
        assert repo.exists("genome_001")
        assert repo.count() == 1

        # 加载
        loaded = repo.load("genome_001")
        assert loaded.genome_id == "genome_001"
        assert loaded.genes["hook"]["type"] == "rescue"
        assert loaded.fitness["roas_d7"] == 0.32
        assert loaded.lineage.source == "winner_001"


def test_ac5b_repository_load_not_found():
    """AC5b: Load non-existent genome raises GenomeNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = GenomeRepository(storage_dir=tmpdir)
        try:
            repo.load("nonexistent")
            assert False, "Expected GenomeNotFoundError"
        except GenomeNotFoundError:
            pass


def test_ac5c_repository_batch():
    """AC5c: Save and load multiple genomes."""
    genomes = []
    for i in range(3):
        genes = {
            "hook": {"type": f"type_{i}", "strength": 0.8},
            "visual": {"style": "fantasy", "composition": "center"},
            "reward": {"type": "unlock", "intensity": 0.7},
            "emotion": {"primary": "curiosity"},
            "gameplay": {"mechanic": "merge"},
        }
        genomes.append(CreativeGenome(
            genome_id=f"genome_{i:03d}",
            parent_id=None,
            generation=0,
            genes=genes,
            fitness={"ctr": 0.1 + i * 0.05},
            lineage=GenomeLineage(source=f"winner_{i:03d}", created_by="dna_mapper"),
        ))

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = GenomeRepository(storage_dir=tmpdir)

        # 批量保存
        paths = repo.save_all(genomes)
        assert len(paths) == 3
        assert repo.count() == 3

        # 批量加载
        loaded = repo.load_all()
        assert len(loaded) == 3
        ids = {g.genome_id for g in loaded}
        assert ids == {"genome_000", "genome_001", "genome_002"}

        # 列出 IDs
        assert set(repo.list_ids()) == {"genome_000", "genome_001", "genome_002"}


def test_ac5d_repository_delete():
    """AC5d: Delete genome from repository."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "character_center"},
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }
    genome = CreativeGenome(
        genome_id="genome_001",
        parent_id=None,
        generation=0,
        genes=genes,
        fitness={"ctr": 0.12},
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = GenomeRepository(storage_dir=tmpdir)
        repo.save(genome)
        assert repo.exists("genome_001")

        repo.delete("genome_001")
        assert not repo.exists("genome_001")
        assert repo.count() == 0


# ═══════════════════════════════════════════════════════════
# AC6 — Exception Hierarchy
# ═══════════════════════════════════════════════════════════

def test_ac6_exception_hierarchy():
    """AC6: All exceptions inherit from GenomeError."""
    assert issubclass(GenomeNotFoundError, GenomeError)
    assert issubclass(GenomeDuplicateError, GenomeError)
    assert issubclass(GenomeValidationError, GenomeError)
    assert issubclass(DNAMappingError, GenomeError)
    assert issubclass(GenomeRepositoryError, GenomeError)

    # 明确错误消息
    exc = GenomeNotFoundError("genome_xxx")
    assert "genome_xxx" in str(exc)

    exc2 = GenomeDuplicateError("genome_dup")
    assert "genome_dup" in str(exc2)

    exc3 = DNAMappingError("bad data", source_id="src_001")
    assert "bad data" in str(exc3)
    assert exc3.source_id == "src_001"