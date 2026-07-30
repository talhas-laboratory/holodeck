"""Deterministic high-recall code-graph sentinels (M2-025).

Sentinels activate attention. They never produce a cleared decision.
Pure domain helpers — no storage, adapter, sqlite, or extractor imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from holodeck_governance.domain.workspace.intelligence.code_graph.entities import (
    CodeEntityFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.paths import (
    normalize_repository_relative_path,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.relations import (
    CodeRelationFact,
)
from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CoverageStatus,
    EntityKind,
    RelationKind,
)


class SentinelKind(StrEnum):
    PUBLIC_EXPORT = "public_export"
    API_ENTRY = "api_entry"
    SCHEMA_OR_MIGRATION = "schema_or_migration"
    MANIFEST = "manifest"
    CONFIGURATION = "configuration"
    TEST_ASSOCIATION = "test_association"
    OWNERSHIP_TAG = "ownership_tag"
    SENSITIVE_PATH_OR_SYMBOL = "sensitive_path_or_symbol"
    PARTIAL_COVERAGE = "partial_coverage"


class SentinelStatus(StrEnum):
    ACTIVATED = "activated"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class SentinelFinding:
    kind: SentinelKind
    status: SentinelStatus
    title: str
    detail: str
    entity_fact_ids: tuple[str, ...] = ()
    path_refs: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status is SentinelStatus.ACTIVATED and self.status.value == "cleared":
            raise ValueError("sentinels must never emit cleared")
        # Defensive: StrEnum cannot be CLEARED, but reject literal misuse.
        if str(self.status).lower() == "cleared":
            raise ValueError("sentinels must never emit cleared")


@dataclass(frozen=True, slots=True)
class SentinelCatalog:
    """Ordered catalog of sentinel kinds evaluated by ``evaluate_sentinels``."""

    kinds: tuple[SentinelKind, ...] = tuple(SentinelKind)


def _path_intersects(path: str, changed: frozenset[str]) -> bool:
    if path in changed:
        return True
    for changed_path in changed:
        if path == changed_path:
            return True
        if path.startswith(changed_path.rstrip("/") + "/"):
            return True
        if changed_path.startswith(path.rstrip("/") + "/"):
            return True
    return False


def _entity_has_all_evidence(entity: CodeEntityFact) -> bool:
    """Detect weak ``__all__`` export hints on entity identity fields."""

    native = (entity.extractor_native_id or "").lower()
    qn = (entity.qualified_name or "").lower()
    return "__all__" in native or "__all__" in qn


def _public_export_entities(
    entities: tuple[CodeEntityFact, ...],
    relations: tuple[CodeRelationFact, ...],
) -> list[CodeEntityFact]:
    exposed_ids: set[str] = set()
    for relation in relations:
        if relation.relation_kind is RelationKind.EXPOSES:
            exposed_ids.add(relation.source_entity_fact_id)
            exposed_ids.add(relation.target_entity_fact_id)

    selected: list[CodeEntityFact] = []
    for entity in entities:
        if entity.entity_kind is EntityKind.API_ENTRY_POINT:
            selected.append(entity)
            continue
        if entity.entity_fact_id in exposed_ids:
            selected.append(entity)
            continue
        if _entity_has_all_evidence(entity) and entity.entity_kind in (
            EntityKind.MODULE,
            EntityKind.CLASS,
            EntityKind.FUNCTION,
            EntityKind.METHOD,
        ):
            selected.append(entity)
    selected.sort(key=lambda entity: entity.entity_key)
    return selected


def _filter_change_mode(
    findings: list[SentinelFinding],
    *,
    changed_paths: frozenset[str],
) -> list[SentinelFinding]:
    """Prefer findings intersecting changed paths; keep global PARTIAL_COVERAGE."""

    if not changed_paths:
        return findings
    kept: list[SentinelFinding] = []
    for finding in findings:
        if finding.kind is SentinelKind.PARTIAL_COVERAGE:
            kept.append(finding)
            continue
        if finding.status is SentinelStatus.UNRESOLVED and not finding.path_refs:
            # Configuration-level unresolved (no tags / empty sensitive lists).
            kept.append(finding)
            continue
        if any(_path_intersects(path, changed_paths) for path in finding.path_refs):
            kept.append(finding)
    return kept


def evaluate_sentinels(
    *,
    entities: tuple[CodeEntityFact, ...] | list[CodeEntityFact],
    relations: tuple[CodeRelationFact, ...] | list[CodeRelationFact],
    coverage_status: CoverageStatus,
    changed_paths: tuple[str, ...] | list[str] = (),
    ownership_tags: tuple[str, ...] | list[str] = (),
    sensitive_path_prefixes: tuple[str, ...] | list[str] = (),
    sensitive_symbols: tuple[str, ...] | list[str] = (),
) -> tuple[SentinelFinding, ...]:
    """Evaluate the sentinel catalog; status is only ACTIVATED or UNRESOLVED."""

    entity_tuple = tuple(entities)
    relation_tuple = tuple(relations)
    changed = frozenset(
        normalize_repository_relative_path(path) for path in changed_paths
    )
    findings: list[SentinelFinding] = []

    # PUBLIC_EXPORT
    public = _public_export_entities(entity_tuple, relation_tuple)
    if changed:
        # High-recall change mode: also surface non-test callables/modules on
        # changed paths as potential public-export attention (never cleared).
        by_id_public = {entity.entity_fact_id: entity for entity in public}
        for entity in entity_tuple:
            if entity.entity_fact_id in by_id_public:
                continue
            if entity.entity_kind is EntityKind.TEST:
                continue
            if entity.repository_relative_path.startswith("tests/"):
                continue
            if entity.entity_kind not in (
                EntityKind.MODULE,
                EntityKind.CLASS,
                EntityKind.FUNCTION,
                EntityKind.METHOD,
            ):
                continue
            if _path_intersects(entity.repository_relative_path, changed):
                public.append(entity)
        public = [
            entity
            for entity in public
            if _path_intersects(entity.repository_relative_path, changed)
        ]
        public.sort(key=lambda entity: entity.entity_key)
    if public:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.PUBLIC_EXPORT,
                status=SentinelStatus.ACTIVATED,
                title="Public export or exposed API surface",
                detail=(
                    f"{len(public)} public-export or EXPOSES-linked entit"
                    f"{'y' if len(public) == 1 else 'ies'} observed"
                ),
                entity_fact_ids=tuple(entity.entity_fact_id for entity in public),
                path_refs=tuple(
                    sorted({entity.repository_relative_path for entity in public})
                ),
                evidence_notes=("api_entry_point_or_exposes_or___all__",),
            )
        )

    # API_ENTRY
    api_entries = sorted(
        (
            entity
            for entity in entity_tuple
            if entity.entity_kind is EntityKind.API_ENTRY_POINT
        ),
        key=lambda entity: entity.entity_key,
    )
    if changed:
        api_entries = [
            entity
            for entity in api_entries
            if _path_intersects(entity.repository_relative_path, changed)
        ]
    if api_entries:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.API_ENTRY,
                status=SentinelStatus.ACTIVATED,
                title="API entry points",
                detail=f"{len(api_entries)} API entry point(s) observed",
                entity_fact_ids=tuple(e.entity_fact_id for e in api_entries),
                path_refs=tuple(
                    sorted({e.repository_relative_path for e in api_entries})
                ),
                evidence_notes=("entity_kind=api_entry_point",),
            )
        )

    # SCHEMA_OR_MIGRATION
    schema_mig = sorted(
        (
            entity
            for entity in entity_tuple
            if entity.entity_kind in (EntityKind.SCHEMA_OBJECT, EntityKind.MIGRATION)
        ),
        key=lambda entity: entity.entity_key,
    )
    migrate_ids = {
        relation.source_entity_fact_id
        for relation in relation_tuple
        if relation.relation_kind is RelationKind.MIGRATES
    } | {
        relation.target_entity_fact_id
        for relation in relation_tuple
        if relation.relation_kind is RelationKind.MIGRATES
    }
    by_id = {entity.entity_fact_id: entity for entity in entity_tuple}
    for fact_id in migrate_ids:
        entity = by_id.get(fact_id)
        if entity is not None and entity not in schema_mig:
            schema_mig.append(entity)
    schema_mig.sort(key=lambda entity: entity.entity_key)
    if changed:
        schema_mig = [
            entity
            for entity in schema_mig
            if _path_intersects(entity.repository_relative_path, changed)
        ]
    if schema_mig:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.SCHEMA_OR_MIGRATION,
                status=SentinelStatus.ACTIVATED,
                title="Schema or migration facts",
                detail=f"{len(schema_mig)} schema/migration-related entit"
                f"{'y' if len(schema_mig) == 1 else 'ies'} observed",
                entity_fact_ids=tuple(e.entity_fact_id for e in schema_mig),
                path_refs=tuple(
                    sorted({e.repository_relative_path for e in schema_mig})
                ),
                evidence_notes=("schema_object_migration_or_migrates",),
            )
        )

    # MANIFEST
    manifests = sorted(
        (e for e in entity_tuple if e.entity_kind is EntityKind.MANIFEST),
        key=lambda entity: entity.entity_key,
    )
    if changed:
        manifests = [
            entity
            for entity in manifests
            if _path_intersects(entity.repository_relative_path, changed)
        ]
    if manifests:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.MANIFEST,
                status=SentinelStatus.ACTIVATED,
                title="Dependency manifests",
                detail=f"{len(manifests)} manifest entit"
                f"{'y' if len(manifests) == 1 else 'ies'} observed",
                entity_fact_ids=tuple(e.entity_fact_id for e in manifests),
                path_refs=tuple(
                    sorted({e.repository_relative_path for e in manifests})
                ),
                evidence_notes=("entity_kind=manifest",),
            )
        )

    # CONFIGURATION
    configs = sorted(
        (e for e in entity_tuple if e.entity_kind is EntityKind.CONFIGURATION),
        key=lambda entity: entity.entity_key,
    )
    if changed:
        configs = [
            entity
            for entity in configs
            if _path_intersects(entity.repository_relative_path, changed)
        ]
    if configs:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.CONFIGURATION,
                status=SentinelStatus.ACTIVATED,
                title="Configuration facts",
                detail=f"{len(configs)} configuration entit"
                f"{'y' if len(configs) == 1 else 'ies'} observed",
                entity_fact_ids=tuple(e.entity_fact_id for e in configs),
                path_refs=tuple(sorted({e.repository_relative_path for e in configs})),
                evidence_notes=("entity_kind=configuration",),
            )
        )

    # TEST_ASSOCIATION
    tests = sorted(
        (e for e in entity_tuple if e.entity_kind is EntityKind.TEST),
        key=lambda entity: entity.entity_key,
    )
    test_rel_ids = {
        relation.source_entity_fact_id
        for relation in relation_tuple
        if relation.relation_kind is RelationKind.TESTS
    } | {
        relation.target_entity_fact_id
        for relation in relation_tuple
        if relation.relation_kind is RelationKind.TESTS
    }
    for fact_id in test_rel_ids:
        entity = by_id.get(fact_id)
        if entity is not None and entity not in tests:
            tests.append(entity)
    tests.sort(key=lambda entity: entity.entity_key)
    evidence_by_id: dict[str, str] = {
        entity.entity_fact_id: "test_or_tests_relation" for entity in tests
    }
    if changed:
        changed_entity_ids = {
            entity.entity_fact_id
            for entity in entity_tuple
            if _path_intersects(entity.repository_relative_path, changed)
        }
        related_via_tests: set[str] = set()
        for relation in relation_tuple:
            if relation.relation_kind is not RelationKind.TESTS:
                continue
            src = relation.source_entity_fact_id
            tgt = relation.target_entity_fact_id
            if src in changed_entity_ids:
                related_via_tests.add(tgt)
            if tgt in changed_entity_ids:
                related_via_tests.add(src)

        selected: list[CodeEntityFact] = []
        evidence_by_id = {}
        seen_ids: set[str] = set()
        for entity in tests:
            on_changed = entity.entity_fact_id in changed_entity_ids
            related = entity.entity_fact_id in related_via_tests
            if not on_changed and not related:
                continue
            if entity.entity_fact_id in seen_ids:
                continue
            seen_ids.add(entity.entity_fact_id)
            selected.append(entity)
            if on_changed and _path_intersects(
                entity.repository_relative_path, changed
            ):
                evidence_by_id[entity.entity_fact_id] = "changed_test"
            else:
                evidence_by_id[entity.entity_fact_id] = "related_test"
        # TESTS neighbors of changed production entities may not already be in
        # ``tests`` (e.g. linked modules); include them as related_test.
        for fact_id in sorted(related_via_tests):
            if fact_id in seen_ids:
                continue
            entity = by_id.get(fact_id)
            if entity is None:
                continue
            seen_ids.add(fact_id)
            selected.append(entity)
            evidence_by_id[fact_id] = "related_test"
        selected.sort(key=lambda entity: entity.entity_key)
        tests = selected
    if tests:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.TEST_ASSOCIATION,
                status=SentinelStatus.ACTIVATED,
                title="Test associations",
                detail=f"{len(tests)} test-related entit"
                f"{'y' if len(tests) == 1 else 'ies'} observed",
                entity_fact_ids=tuple(e.entity_fact_id for e in tests),
                path_refs=tuple(sorted({e.repository_relative_path for e in tests})),
                evidence_notes=tuple(
                    evidence_by_id.get(e.entity_fact_id, "test_or_tests_relation")
                    for e in tests
                ),
            )
        )

    # OWNERSHIP_TAG
    ownership_norm = tuple(
        normalize_repository_relative_path(tag) for tag in ownership_tags if tag.strip()
    )
    if not ownership_norm:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.OWNERSHIP_TAG,
                status=SentinelStatus.UNRESOLVED,
                title="Ownership tags",
                detail="no ownership tags configured",
                evidence_notes=("ownership_tags_empty",),
            )
        )
    else:
        owned = [
            entity
            for entity in entity_tuple
            if any(
                _path_intersects(entity.repository_relative_path, frozenset({tag}))
                for tag in ownership_norm
            )
        ]
        owned.sort(key=lambda entity: entity.entity_key)
        if changed:
            owned = [
                entity
                for entity in owned
                if _path_intersects(entity.repository_relative_path, changed)
            ]
        if owned:
            findings.append(
                SentinelFinding(
                    kind=SentinelKind.OWNERSHIP_TAG,
                    status=SentinelStatus.ACTIVATED,
                    title="Ownership-tagged paths",
                    detail=f"{len(owned)} entit"
                    f"{'y' if len(owned) == 1 else 'ies'} match ownership tags",
                    entity_fact_ids=tuple(e.entity_fact_id for e in owned),
                    path_refs=tuple(
                        sorted({e.repository_relative_path for e in owned})
                    ),
                    evidence_notes=("ownership_tag_path_match",),
                )
            )
        else:
            findings.append(
                SentinelFinding(
                    kind=SentinelKind.OWNERSHIP_TAG,
                    status=SentinelStatus.UNRESOLVED,
                    title="Ownership tags",
                    detail="ownership tags configured but no matching entities",
                    path_refs=ownership_norm,
                    evidence_notes=("ownership_tags_no_match",),
                )
            )

    # SENSITIVE_PATH_OR_SYMBOL
    prefixes = tuple(
        normalize_repository_relative_path(prefix)
        for prefix in sensitive_path_prefixes
        if prefix.strip()
    )
    symbols = tuple(symbol for symbol in sensitive_symbols if symbol.strip())
    if not prefixes and not symbols:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.SENSITIVE_PATH_OR_SYMBOL,
                status=SentinelStatus.UNRESOLVED,
                title="Sensitive paths or symbols",
                detail="no sensitive path prefixes or symbols configured",
                evidence_notes=("sensitive_lists_empty",),
            )
        )
    else:
        sensitive: list[CodeEntityFact] = []
        for entity in entity_tuple:
            path_hit = any(
                entity.repository_relative_path == prefix
                or entity.repository_relative_path.startswith(prefix.rstrip("/") + "/")
                for prefix in prefixes
            )
            symbol_hit = False
            if symbols and entity.qualified_name is not None:
                symbol_hit = any(symbol in entity.qualified_name for symbol in symbols)
            if path_hit or symbol_hit:
                sensitive.append(entity)
        sensitive.sort(key=lambda entity: entity.entity_key)
        if changed:
            sensitive = [
                entity
                for entity in sensitive
                if _path_intersects(entity.repository_relative_path, changed)
            ]
        if sensitive:
            findings.append(
                SentinelFinding(
                    kind=SentinelKind.SENSITIVE_PATH_OR_SYMBOL,
                    status=SentinelStatus.ACTIVATED,
                    title="Sensitive path or symbol match",
                    detail=f"{len(sensitive)} entit"
                    f"{'y' if len(sensitive) == 1 else 'ies'} match sensitive lists",
                    entity_fact_ids=tuple(e.entity_fact_id for e in sensitive),
                    path_refs=tuple(
                        sorted({e.repository_relative_path for e in sensitive})
                    ),
                    evidence_notes=("sensitive_path_or_symbol_match",),
                )
            )
        else:
            findings.append(
                SentinelFinding(
                    kind=SentinelKind.SENSITIVE_PATH_OR_SYMBOL,
                    status=SentinelStatus.UNRESOLVED,
                    title="Sensitive paths or symbols",
                    detail="sensitive lists configured but no matching entities",
                    evidence_notes=("sensitive_lists_no_match",),
                )
            )

    # PARTIAL_COVERAGE (global; not filtered by changed_paths)
    if coverage_status is CoverageStatus.PARTIAL:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.PARTIAL_COVERAGE,
                status=SentinelStatus.ACTIVATED,
                title="Partial graph coverage",
                detail="snapshot coverage_status is partial",
                evidence_notes=("coverage_status=partial",),
            )
        )
    elif coverage_status is CoverageStatus.UNKNOWN:
        findings.append(
            SentinelFinding(
                kind=SentinelKind.PARTIAL_COVERAGE,
                status=SentinelStatus.UNRESOLVED,
                title="Unknown graph coverage",
                detail="snapshot coverage_status is unknown",
                evidence_notes=("coverage_status=unknown",),
            )
        )

    if changed:
        findings = _filter_change_mode(findings, changed_paths=changed)

    # Stable order by kind then title.
    findings.sort(
        key=lambda finding: (finding.kind.value, finding.title, finding.detail)
    )
    for finding in findings:
        if finding.status.value == "cleared":  # pragma: no cover - invariant
            raise ValueError("sentinels must never emit cleared")
    return tuple(findings)
