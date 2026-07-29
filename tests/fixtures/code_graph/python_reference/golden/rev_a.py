"""Typed golden facts for python_reference rev_a.

These are Holodeck domain facts, not provider-native output. Extractors must
converge on this vocabulary; they may use different native ids.
"""

from __future__ import annotations

from datetime import UTC, datetime

from holodeck_governance.domain.workspace.intelligence.code_graph import (
    UNRESOLVED_DYNAMIC_CALL,
    CodeEntityFact,
    CodeRelationFact,
    EntityKind,
    ExtractionDiagnostic,
    ObservationMethod,
    RelationKind,
    SourceSpan,
    build_entity_key,
)

# Stable fixture ids (UUIDv7 layout) so golden comparisons stay deterministic.
TENANT = "01900000-0000-7000-8000-00000000a001"
WORKSPACE = "01900000-0000-7000-8000-00000000a002"
BINDING = "01900000-0000-7000-8000-00000000a003"
SOURCE = "01900000-0000-7000-8000-00000000a010"
OBSERVATION = "01900000-0000-7000-8000-00000000a011"
NOW = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)

# Relation kinds intentionally absent from this Python fixture snapshot.
# None deferred: every initial relation kind is represented below.
DEFERRED_RELATION_KINDS_FROM_PYTHON_FIXTURE: frozenset[RelationKind] = frozenset()


def _eid(suffix: str) -> str:
    return f"01900000-0000-7000-8000-00000000b{suffix}"


def _rid(suffix: str) -> str:
    return f"01900000-0000-7000-8000-00000000c{suffix}"


def _entity(
    *,
    suffix: str,
    kind: EntityKind,
    path: str,
    qualified_name: str | None = None,
    language: str | None = "python",
    span: SourceSpan | None = None,
) -> CodeEntityFact:
    return CodeEntityFact(
        entity_fact_id=_eid(suffix),
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        repository_binding_id=BINDING,
        entity_key=build_entity_key(
            entity_kind=kind,
            repository_relative_path=path,
            qualified_name=qualified_name,
        ),
        entity_kind=kind,
        repository_relative_path=path,
        source_id=SOURCE,
        source_observation_id=OBSERVATION,
        observation_method=ObservationMethod.DIRECT_PARSE,
        created_at=NOW,
        language=language,
        qualified_name=qualified_name,
        span=span,
    )


def _relation(
    *,
    suffix: str,
    kind: RelationKind,
    source: CodeEntityFact,
    target: CodeEntityFact,
    span: SourceSpan | None = None,
    method: ObservationMethod = ObservationMethod.DIRECT_PARSE,
) -> CodeRelationFact:
    return CodeRelationFact(
        relation_fact_id=_rid(suffix),
        tenant_id=TENANT,
        workspace_object_id=WORKSPACE,
        repository_binding_id=BINDING,
        relation_kind=kind,
        source_entity_fact_id=source.entity_fact_id,
        target_entity_fact_id=target.entity_fact_id,
        evidence_source_id=SOURCE,
        evidence_observation_id=OBSERVATION,
        observation_method=method,
        created_at=NOW,
        evidence_span=span,
    )


def golden_entities_rev_a() -> tuple[CodeEntityFact, ...]:
    return (
        _entity(suffix="001", kind=EntityKind.REPOSITORY, path=".", language=None),
        _entity(suffix="002", kind=EntityKind.DIRECTORY, path="sample_app", language=None),
        _entity(suffix="003", kind=EntityKind.DIRECTORY, path="migrations", language=None),
        _entity(suffix="004", kind=EntityKind.DIRECTORY, path="config", language=None),
        _entity(suffix="005", kind=EntityKind.DIRECTORY, path="tests", language=None),
        _entity(
            suffix="010",
            kind=EntityKind.MANIFEST,
            path="pyproject.toml",
            language=None,
            qualified_name="sample-app",
        ),
        _entity(
            suffix="011",
            kind=EntityKind.CONFIGURATION,
            path="config/settings.toml",
            language=None,
            qualified_name="app",
        ),
        _entity(
            suffix="020",
            kind=EntityKind.MODULE,
            path="sample_app/base.py",
            qualified_name="sample_app.base",
        ),
        _entity(
            suffix="021",
            kind=EntityKind.CLASS,
            path="sample_app/base.py",
            qualified_name="sample_app.base.Animal",
            span=SourceSpan(start_line=4, end_line=11),
        ),
        _entity(
            suffix="022",
            kind=EntityKind.METHOD,
            path="sample_app/base.py",
            qualified_name="sample_app.base.Animal.label",
            span=SourceSpan(start_line=9, end_line=10),
        ),
        _entity(
            suffix="030",
            kind=EntityKind.MODULE,
            path="sample_app/service.py",
            qualified_name="sample_app.service",
        ),
        _entity(
            suffix="031",
            kind=EntityKind.CLASS,
            path="sample_app/service.py",
            qualified_name="sample_app.service.Greeter",
            span=SourceSpan(start_line=8, end_line=24),
        ),
        _entity(
            suffix="032",
            kind=EntityKind.METHOD,
            path="sample_app/service.py",
            qualified_name="sample_app.service.Greeter.greet",
            span=SourceSpan(start_line=15, end_line=18),
        ),
        _entity(
            suffix="033",
            kind=EntityKind.METHOD,
            path="sample_app/service.py",
            qualified_name="sample_app.service.Greeter.invoke",
            span=SourceSpan(start_line=20, end_line=23),
        ),
        _entity(
            suffix="040",
            kind=EntityKind.MODULE,
            path="sample_app/api.py",
            qualified_name="sample_app.api",
        ),
        _entity(
            suffix="041",
            kind=EntityKind.FUNCTION,
            path="sample_app/api.py",
            qualified_name="sample_app.api.create_app",
            span=SourceSpan(start_line=6, end_line=8),
        ),
        _entity(
            suffix="042",
            kind=EntityKind.API_ENTRY_POINT,
            path="sample_app/api.py",
            qualified_name="sample_app.api.handle_greet",
            span=SourceSpan(start_line=11, end_line=15),
        ),
        _entity(
            suffix="050",
            kind=EntityKind.MODULE,
            path="sample_app/store.py",
            qualified_name="sample_app.store",
        ),
        _entity(
            suffix="051",
            kind=EntityKind.CLASS,
            path="sample_app/store.py",
            qualified_name="sample_app.store.ItemStore",
            span=SourceSpan(start_line=8, end_line=17),
        ),
        _entity(
            suffix="052",
            kind=EntityKind.METHOD,
            path="sample_app/store.py",
            qualified_name="sample_app.store.ItemStore.read_message",
            span=SourceSpan(start_line=12, end_line=13),
        ),
        _entity(
            suffix="053",
            kind=EntityKind.METHOD,
            path="sample_app/store.py",
            qualified_name="sample_app.store.ItemStore.write_message",
            span=SourceSpan(start_line=15, end_line=17),
        ),
        _entity(
            suffix="054",
            kind=EntityKind.FILE,
            path="data/items.json",
            language=None,
            qualified_name="data/items.json",
        ),
        _entity(
            suffix="060",
            kind=EntityKind.MODULE,
            path="sample_app/schema.py",
            qualified_name="sample_app.schema",
        ),
        _entity(
            suffix="061",
            kind=EntityKind.SCHEMA_OBJECT,
            path="sample_app/schema.py",
            qualified_name="sample_app.schema.ITEM_SCHEMA",
            span=SourceSpan(start_line=3, end_line=10),
        ),
        _entity(
            suffix="070",
            kind=EntityKind.MIGRATION,
            path="migrations/001_init.py",
            qualified_name="migrations.001_init.upgrade",
            span=SourceSpan(start_line=6, end_line=7),
        ),
        _entity(
            suffix="080",
            kind=EntityKind.TEST,
            path="tests/test_service.py",
            qualified_name="tests.test_service.test_greeter_message",
            span=SourceSpan(start_line=4, end_line=5),
        ),
        _entity(
            suffix="081",
            kind=EntityKind.TEST,
            path="tests/test_api.py",
            qualified_name="tests.test_api.test_handle_greet",
            span=SourceSpan(start_line=4, end_line=5),
        ),
    )


def _by_qn(entities: tuple[CodeEntityFact, ...], qualified_name: str) -> CodeEntityFact:
    for entity in entities:
        if entity.qualified_name == qualified_name:
            return entity
    raise KeyError(qualified_name)


def _by_kind_path(
    entities: tuple[CodeEntityFact, ...], kind: EntityKind, path: str
) -> CodeEntityFact:
    for entity in entities:
        if entity.entity_kind is kind and entity.repository_relative_path == path:
            return entity
    raise KeyError((kind, path))


def golden_relations_rev_a(
    entities: tuple[CodeEntityFact, ...] | None = None,
) -> tuple[CodeRelationFact, ...]:
    ents = entities or golden_entities_rev_a()
    repo = _by_kind_path(ents, EntityKind.REPOSITORY, ".")
    sample_dir = _by_kind_path(ents, EntityKind.DIRECTORY, "sample_app")
    service_mod = _by_qn(ents, "sample_app.service")
    base_mod = _by_qn(ents, "sample_app.base")
    store_mod = _by_qn(ents, "sample_app.store")
    api_mod = _by_qn(ents, "sample_app.api")
    animal = _by_qn(ents, "sample_app.base.Animal")
    greeter = _by_qn(ents, "sample_app.service.Greeter")
    greet = _by_qn(ents, "sample_app.service.Greeter.greet")
    write = _by_qn(ents, "sample_app.store.ItemStore.write_message")
    read = _by_qn(ents, "sample_app.store.ItemStore.read_message")
    items = _by_kind_path(ents, EntityKind.FILE, "data/items.json")
    handle = _by_qn(ents, "sample_app.api.handle_greet")
    create_app = _by_qn(ents, "sample_app.api.create_app")
    settings = _by_kind_path(ents, EntityKind.CONFIGURATION, "config/settings.toml")
    store_cls = _by_qn(ents, "sample_app.store.ItemStore")
    migration = _by_qn(ents, "migrations.001_init.upgrade")
    schema = _by_qn(ents, "sample_app.schema.ITEM_SCHEMA")
    test_service = _by_qn(ents, "tests.test_service.test_greeter_message")
    test_api = _by_qn(ents, "tests.test_api.test_handle_greet")
    return (
        _relation(suffix="001", kind=RelationKind.CONTAINS, source=repo, target=sample_dir),
        _relation(
            suffix="002",
            kind=RelationKind.DEFINES,
            source=service_mod,
            target=greeter,
            span=SourceSpan(start_line=8, end_line=8),
        ),
        _relation(
            suffix="003",
            kind=RelationKind.IMPORTS,
            source=service_mod,
            target=base_mod,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=3, end_line=3),
        ),
        _relation(
            suffix="004",
            kind=RelationKind.IMPORTS,
            source=service_mod,
            target=store_mod,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=4, end_line=4),
        ),
        _relation(
            suffix="005",
            kind=RelationKind.INHERITS,
            source=greeter,
            target=animal,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=8, end_line=8),
        ),
        _relation(
            suffix="006",
            kind=RelationKind.CALLS,
            source=greet,
            target=write,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=17, end_line=17),
        ),
        _relation(
            suffix="007",
            kind=RelationKind.CALLS,
            source=handle,
            target=create_app,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=12, end_line=12),
        ),
        _relation(
            suffix="008",
            kind=RelationKind.CALLS,
            source=handle,
            target=greet,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=15, end_line=15),
        ),
        _relation(
            suffix="009",
            kind=RelationKind.WRITES,
            source=write,
            target=items,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=17, end_line=17),
        ),
        _relation(
            suffix="010",
            kind=RelationKind.READS,
            source=read,
            target=items,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=13, end_line=13),
        ),
        _relation(
            suffix="011",
            kind=RelationKind.EXPOSES,
            source=api_mod,
            target=handle,
            span=SourceSpan(start_line=11, end_line=11),
        ),
        _relation(
            suffix="012",
            kind=RelationKind.HANDLES,
            source=handle,
            target=greet,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=15, end_line=15),
        ),
        _relation(
            suffix="013",
            kind=RelationKind.TESTS,
            source=test_service,
            target=greet,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=5, end_line=5),
        ),
        _relation(
            suffix="014",
            kind=RelationKind.TESTS,
            source=test_api,
            target=handle,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=5, end_line=5),
        ),
        _relation(
            suffix="015",
            kind=RelationKind.CONFIGURES,
            source=settings,
            target=store_cls,
            method=ObservationMethod.STATICALLY_RESOLVED,
        ),
        _relation(
            suffix="016",
            kind=RelationKind.MIGRATES,
            source=migration,
            target=schema,
            method=ObservationMethod.STATICALLY_RESOLVED,
            span=SourceSpan(start_line=7, end_line=7),
        ),
    )


def golden_diagnostics_rev_a() -> tuple[ExtractionDiagnostic, ...]:
    return (
        ExtractionDiagnostic(
            code=UNRESOLVED_DYNAMIC_CALL,
            message=(
                "Greeter.invoke resolves a handler through globals()[handler_name]; "
                "no CALLS edge is emitted"
            ),
            repository_relative_path="sample_app/service.py",
        ),
    )


def golden_paths_rev_a() -> tuple[tuple[str, ...], ...]:
    """Example evidence paths M3 may later request (entity qualified names)."""

    return (
        (
            "sample_app.api.handle_greet",
            "sample_app.service.Greeter.greet",
            "sample_app.store.ItemStore.write_message",
            "data/items.json",
        ),
        (
            "tests.test_service.test_greeter_message",
            "sample_app.service.Greeter.greet",
        ),
        (
            "migrations.001_init.upgrade",
            "sample_app.schema.ITEM_SCHEMA",
        ),
    )
