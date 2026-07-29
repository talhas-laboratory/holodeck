"""Python standard-library AST factual extractor (selected M2 provider).

Never executes repository code. Emits only syntax-backed or deterministic
repository-metadata facts. Dynamic dispatch becomes diagnostics, not CALLS.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from holodeck_governance.application.repository_extractor import (
    ExtractionCoverage,
    ExtractionRequest,
    ExtractionResult,
    ExtractorCapabilities,
    PathSourceBinding,
    ProviderDescriptor,
)
from holodeck_governance.domain.workspace.intelligence.code_graph import (
    UNRESOLVED_DYNAMIC_CALL,
    CodeEntityFact,
    CodeGraphReason,
    CodeRelationFact,
    CoverageStatus,
    EntityKind,
    ExtractionDiagnostic,
    ObservationMethod,
    RelationKind,
    SourceSpan,
    build_entity_key,
    code_graph_error,
    normalize_repository_relative_path,
)

PYTHON_AST_PROVIDER_KEY = "python_stdlib_ast"
PYTHON_AST_PROVIDER_SCHEMA = "m2.python_stdlib_ast.v1"
PYTHON_AST_PROVIDER_VERSION = f"python:{sys.version_info.major}.{sys.version_info.minor}"
_CREATED_AT = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)
_SKIP_DIR_NAMES = frozenset({".git", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache"})
_CONFIG_SUFFIXES = frozenset({".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"})
_MANIFEST_NAMES = frozenset({"pyproject.toml", "setup.cfg", "setup.py", "Cargo.toml"})


def _configuration_hash() -> str:
    payload = f"{PYTHON_AST_PROVIDER_KEY}|{PYTHON_AST_PROVIDER_SCHEMA}|extract.v1"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


_PROVIDER = ProviderDescriptor(
    provider_key=PYTHON_AST_PROVIDER_KEY,
    provider_version=PYTHON_AST_PROVIDER_VERSION,
    provider_schema_version=PYTHON_AST_PROVIDER_SCHEMA,
    configuration_hash=_configuration_hash(),
)


def deterministic_uuidv7(seed: str) -> str:
    """Stable UUIDv7-shaped id derived from a seed (for byte-stable candidates)."""

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    millis = int.from_bytes(digest[:6], "big") & ((1 << 48) - 1)
    rand = digest[6:16]
    value = (millis & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= (int.from_bytes(rand[:2], "big") & 0x0FFF) << 64
    value |= 0b10 << 62
    value |= int.from_bytes(rand[2:], "big") & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


def tree_content_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in _iter_repo_files(root):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _iter_repo_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        files.append(path)
    return tuple(files)


@dataclass
class _EntityAcc:
    entities: dict[str, CodeEntityFact] = field(default_factory=dict)
    # qualified_name / module alias -> entity_key
    symbols: dict[str, str] = field(default_factory=dict)
    path_modules: dict[str, str] = field(default_factory=dict)


@dataclass
class _RelationAcc:
    relations: list[CodeRelationFact] = field(default_factory=list)
    seen: set[tuple[str, str, str]] = field(default_factory=set)


class PythonStdlibAstExtractor:
    """Production-compatible Python factual extractor using stdlib ast only."""

    def describe_capabilities(self) -> ExtractorCapabilities:
        return ExtractorCapabilities(
            provider=_PROVIDER,
            languages=("python",),
            entity_kinds=tuple(kind.value for kind in EntityKind),
            relation_kinds=tuple(kind.value for kind in RelationKind),
            supports_incremental=True,
            supports_offline=True,
            notes=(
                "stdlib ast only; no Tree-sitter/GitNexus/Joern dependency",
                "dynamic dispatch and ambiguous calls are diagnostics",
            ),
        )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        root = request.repository_path.resolve()
        if not root.exists() or not root.is_dir():
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "repository_path must be an existing directory",
            )
        if "python" not in request.language_allowlist:
            raise code_graph_error(
                CodeGraphReason.MALFORMED_FACT,
                "python_stdlib_ast requires python in language_allowlist",
            )

        before = self._actual_revision(root, request.requested_revision)
        if before != request.requested_revision:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "checkout revision does not match requested_revision before extraction",
            )

        started = time.monotonic()
        diagnostics: list[ExtractionDiagnostic] = []
        entities = _EntityAcc()
        relations = _RelationAcc()
        bindings = {
            normalize_repository_relative_path(item.repository_relative_path): item
            for item in request.path_source_bindings
        }

        self._emit_repository_scaffold(request, root, entities, relations, bindings)

        files = self._select_files(root, request, diagnostics)
        parsed: list[tuple[str, Path, ast.AST, str, str, str]] = []
        for path in files:
            if request.limits.max_seconds is not None:
                if time.monotonic() - started > request.limits.max_seconds:
                    diagnostics.append(
                        ExtractionDiagnostic(
                            code="time_limit",
                            message="max_seconds budget exhausted",
                        )
                    )
                    break
            relative = path.relative_to(root).as_posix()
            if request.limits.max_file_bytes is not None:
                size = path.stat().st_size
                if size > request.limits.max_file_bytes:
                    diagnostics.append(
                        ExtractionDiagnostic(
                            code="file_too_large",
                            message=f"file exceeds max_file_bytes ({size})",
                            repository_relative_path=relative,
                        )
                    )
                    continue
            source_id, observation_id = self._source_for(
                request=request, relative=relative, bindings=bindings
            )
            tree = self._ingest_file_entities(
                request=request,
                path=path,
                relative=relative,
                entities=entities,
                relations=relations,
                bindings=bindings,
                diagnostics=diagnostics,
                source_id=source_id,
                observation_id=observation_id,
            )
            if tree is not None:
                parsed.append(
                    (relative, path, tree, source_id, observation_id, hashlib.sha256(path.read_bytes()).hexdigest())
                )
            if (
                request.limits.max_entities is not None
                and len(entities.entities) >= request.limits.max_entities
            ):
                diagnostics.append(
                    ExtractionDiagnostic(
                        code="entity_limit",
                        message="max_entities budget reached",
                    )
                )
                break

        for relative, path, tree, source_id, observation_id, _content_hash in parsed:
            self._ingest_file_relations(
                request=request,
                relative=relative,
                tree=tree,
                entities=entities,
                relations=relations,
                source_id=source_id,
                observation_id=observation_id,
                diagnostics=diagnostics,
            )

        for entity in list(entities.entities.values()):
            if entity.entity_kind is EntityKind.CONFIGURATION:
                source_id, observation_id = self._source_for(
                    request=request,
                    relative=entity.repository_relative_path,
                    bindings=bindings,
                )
                self._emit_configures(
                    request=request,
                    relative=entity.repository_relative_path,
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                )

        after = self._actual_revision(root, request.requested_revision)
        if after != before:
            raise code_graph_error(
                CodeGraphReason.REVISION_MISMATCH,
                "repository content changed during extraction",
            )

        entity_tuple = tuple(
            entities.entities[key] for key in sorted(entities.entities)
        )
        relation_tuple = tuple(relations.relations)
        if (
            request.limits.max_relations is not None
            and len(relation_tuple) > request.limits.max_relations
        ):
            relation_tuple = relation_tuple[: request.limits.max_relations]
            diagnostics.append(
                ExtractionDiagnostic(
                    code="relation_limit",
                    message="max_relations budget truncated relations",
                )
            )

        coverage = (
            CoverageStatus.PARTIAL
            if diagnostics
            else CoverageStatus.COMPLETE
        )
        notes: tuple[str, ...] = ()
        if coverage is CoverageStatus.PARTIAL:
            notes = (
                f"{len(diagnostics)} diagnostic(s); "
                f"{len(entity_tuple)} entities; {len(relation_tuple)} relations",
            )
        return ExtractionResult(
            actual_revision=after,
            provider=_PROVIDER,
            candidate_entities=entity_tuple,
            candidate_relations=relation_tuple,
            diagnostics=tuple(diagnostics),
            coverage=ExtractionCoverage(status=coverage, notes=notes),
        )

    def _actual_revision(self, root: Path, requested: str) -> str:
        if requested.startswith("fixture:"):
            return f"fixture:{tree_content_hash(root)}"
        git = root / ".git"
        if git.exists():
            head = root / ".git" / "HEAD"
            # Shallow read without spawning git when possible.
            text = head.read_text(encoding="utf-8").strip()
            if text.startswith("ref:"):
                ref = text.split(" ", 1)[1].strip()
                ref_path = root / ".git" / ref
                if ref_path.is_file():
                    return ref_path.read_text(encoding="utf-8").strip()[:40]
            elif len(text) >= 7:
                return text[:40]
        marker = root / "REVISION"
        if marker.is_file():
            return marker.read_text(encoding="utf-8").strip()
        return requested

    def _select_files(
        self,
        root: Path,
        request: ExtractionRequest,
        diagnostics: list[ExtractionDiagnostic],
    ) -> list[Path]:
        selected: list[Path] = []
        for path in _iter_repo_files(root):
            relative = path.relative_to(root).as_posix()
            if request.path_includes and not any(
                relative == inc or relative.startswith(inc.rstrip("/") + "/")
                for inc in request.path_includes
            ):
                continue
            if any(
                relative == exc or relative.startswith(exc.rstrip("/") + "/")
                for exc in request.path_excludes
            ):
                diagnostics.append(
                    ExtractionDiagnostic(
                        code="path_excluded",
                        message="path excluded by request",
                        repository_relative_path=relative,
                    )
                )
                continue
            selected.append(path)
        if request.limits.max_files is not None:
            if len(selected) > request.limits.max_files:
                diagnostics.append(
                    ExtractionDiagnostic(
                        code="file_limit",
                        message="max_files budget truncated file set",
                    )
                )
            selected = selected[: request.limits.max_files]
        return selected

    def _source_for(
        self,
        *,
        request: ExtractionRequest,
        relative: str,
        bindings: dict[str, PathSourceBinding],
    ) -> tuple[str, str]:
        key = normalize_repository_relative_path(relative) if relative != "." else "."
        if relative == ".":
            key = "."
        bound = bindings.get(key)
        if bound is not None:
            return bound.source_id, bound.source_observation_id
        seed = f"{request.requested_revision}|{key}"
        return (
            deterministic_uuidv7(f"source|{seed}"),
            deterministic_uuidv7(f"observation|{seed}"),
        )

    def _add_entity(
        self,
        entities: _EntityAcc,
        *,
        request: ExtractionRequest,
        kind: EntityKind,
        path: str,
        qualified_name: str | None,
        source_id: str,
        observation_id: str,
        language: str | None,
        span: SourceSpan | None = None,
        content_hash: str | None = None,
    ) -> CodeEntityFact:
        entity_key = build_entity_key(
            entity_kind=kind,
            repository_relative_path=path,
            qualified_name=qualified_name,
        )
        existing = entities.entities.get(entity_key)
        if existing is not None:
            return existing
        entity = CodeEntityFact(
            entity_fact_id=deterministic_uuidv7(f"entity|{entity_key}"),
            tenant_id=request.tenant_id,
            workspace_object_id=request.workspace_object_id,
            repository_binding_id=request.repository_binding_id,
            entity_key=entity_key,
            entity_kind=kind,
            repository_relative_path=path,
            source_id=source_id,
            source_observation_id=observation_id,
            observation_method=ObservationMethod.DIRECT_PARSE,
            created_at=_CREATED_AT,
            language=language,
            qualified_name=qualified_name,
            span=span,
            content_hash=content_hash,
        )
        entities.entities[entity_key] = entity
        if qualified_name:
            entities.symbols[qualified_name] = entity_key
        return entity

    def _add_relation(
        self,
        relations: _RelationAcc,
        *,
        request: ExtractionRequest,
        kind: RelationKind,
        source: CodeEntityFact,
        target: CodeEntityFact,
        source_id: str,
        observation_id: str,
        method: ObservationMethod = ObservationMethod.DIRECT_PARSE,
        span: SourceSpan | None = None,
    ) -> None:
        token = (kind.value, source.entity_key, target.entity_key)
        if token in relations.seen:
            return
        relations.seen.add(token)
        relations.relations.append(
            CodeRelationFact(
                relation_fact_id=deterministic_uuidv7(
                    f"relation|{kind.value}|{source.entity_key}|{target.entity_key}"
                ),
                tenant_id=request.tenant_id,
                workspace_object_id=request.workspace_object_id,
                repository_binding_id=request.repository_binding_id,
                relation_kind=kind,
                source_entity_fact_id=source.entity_fact_id,
                target_entity_fact_id=target.entity_fact_id,
                evidence_source_id=source_id,
                evidence_observation_id=observation_id,
                observation_method=method,
                created_at=_CREATED_AT,
                evidence_span=span,
            )
        )

    def _emit_repository_scaffold(
        self,
        request: ExtractionRequest,
        root: Path,
        entities: _EntityAcc,
        relations: _RelationAcc,
        bindings: dict[str, PathSourceBinding],
    ) -> None:
        source_id, observation_id = self._source_for(
            request=request, relative=".", bindings=bindings
        )
        repo = self._add_entity(
            entities,
            request=request,
            kind=EntityKind.REPOSITORY,
            path=".",
            qualified_name=None,
            source_id=source_id,
            observation_id=observation_id,
            language=None,
        )
        dirs = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_dir()
            and not any(part in _SKIP_DIR_NAMES for part in path.relative_to(root).parts)
        }
        for directory in sorted(dirs):
            d_source, d_obs = self._source_for(
                request=request, relative=directory, bindings=bindings
            )
            directory_entity = self._add_entity(
                entities,
                request=request,
                kind=EntityKind.DIRECTORY,
                path=directory,
                qualified_name=None,
                source_id=d_source,
                observation_id=d_obs,
                language=None,
            )
            parent = str(Path(directory).parent.as_posix())
            if parent in {".", ""}:
                parent_entity = repo
            else:
                p_source, p_obs = self._source_for(
                    request=request, relative=parent, bindings=bindings
                )
                parent_entity = self._add_entity(
                    entities,
                    request=request,
                    kind=EntityKind.DIRECTORY,
                    path=parent,
                    qualified_name=None,
                    source_id=p_source,
                    observation_id=p_obs,
                    language=None,
                )
            self._add_relation(
                relations,
                request=request,
                kind=RelationKind.CONTAINS,
                source=parent_entity,
                target=directory_entity,
                source_id=d_source,
                observation_id=d_obs,
            )

    def _ingest_file_entities(
        self,
        *,
        request: ExtractionRequest,
        path: Path,
        relative: str,
        entities: _EntityAcc,
        relations: _RelationAcc,
        bindings: dict[str, PathSourceBinding],
        diagnostics: list[ExtractionDiagnostic],
        source_id: str,
        observation_id: str,
    ) -> ast.AST | None:
        content = path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        name = path.name
        if name in _MANIFEST_NAMES or relative.endswith("/pyproject.toml"):
            self._add_entity(
                entities,
                request=request,
                kind=EntityKind.MANIFEST,
                path=relative,
                qualified_name=path.stem,
                source_id=source_id,
                observation_id=observation_id,
                language=None,
                content_hash=content_hash,
            )
            return None
        if path.suffix.lower() in _CONFIG_SUFFIXES and (
            relative.startswith("config/") or "/config/" in relative
        ):
            self._add_entity(
                entities,
                request=request,
                kind=EntityKind.CONFIGURATION,
                path=relative,
                qualified_name=path.stem,
                source_id=source_id,
                observation_id=observation_id,
                language=None,
                content_hash=content_hash,
            )
            return None
        if path.suffix != ".py":
            self._add_entity(
                entities,
                request=request,
                kind=EntityKind.FILE,
                path=relative,
                qualified_name=relative,
                source_id=source_id,
                observation_id=observation_id,
                language=None,
                content_hash=content_hash,
            )
            return None

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(
                ExtractionDiagnostic(
                    code="binary_or_non_utf8",
                    message="python file is not utf-8 text",
                    repository_relative_path=relative,
                )
            )
            return None
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as exc:
            diagnostics.append(
                ExtractionDiagnostic(
                    code="python_syntax_error",
                    message=str(exc).strip() or "syntax error",
                    repository_relative_path=relative,
                )
            )
            return None

        module_qn = _module_qualified_name(relative)
        file_entity = self._add_entity(
            entities,
            request=request,
            kind=EntityKind.FILE,
            path=relative,
            qualified_name=relative,
            source_id=source_id,
            observation_id=observation_id,
            language="python",
            content_hash=content_hash,
        )
        module_entity = self._add_entity(
            entities,
            request=request,
            kind=EntityKind.MODULE,
            path=relative,
            qualified_name=module_qn,
            source_id=source_id,
            observation_id=observation_id,
            language="python",
            content_hash=content_hash,
        )
        entities.path_modules[relative] = module_entity.entity_key
        entities.symbols[module_qn] = module_entity.entity_key
        parent_dir = str(Path(relative).parent.as_posix())
        if parent_dir not in {".", ""}:
            dir_source, dir_obs = self._source_for(
                request=request, relative=parent_dir, bindings=bindings
            )
            directory = self._add_entity(
                entities,
                request=request,
                kind=EntityKind.DIRECTORY,
                path=parent_dir,
                qualified_name=None,
                source_id=dir_source,
                observation_id=dir_obs,
                language=None,
            )
            self._add_relation(
                relations,
                request=request,
                kind=RelationKind.CONTAINS,
                source=directory,
                target=file_entity,
                source_id=source_id,
                observation_id=observation_id,
            )

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._emit_class_entities(
                    node,
                    request=request,
                    relative=relative,
                    module_qn=module_qn,
                    module_entity=module_entity,
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._emit_function_entity(
                    node,
                    request=request,
                    relative=relative,
                    module_qn=module_qn,
                    module_entity=module_entity,
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                )
            elif isinstance(node, ast.Assign):
                self._handle_schema_assign(
                    node,
                    request=request,
                    relative=relative,
                    module_qn=module_qn,
                    module_entity=module_entity,
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                )
            # Capture default Path("...") on ItemStore-like classes for IO edges.
            if isinstance(node, ast.ClassDef):
                self._capture_store_path_defaults(
                    node,
                    request=request,
                    class_qn=f"{module_qn}.{node.name}",
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                )
        return tree

    def _ingest_file_relations(
        self,
        *,
        request: ExtractionRequest,
        relative: str,
        tree: ast.AST,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
        diagnostics: list[ExtractionDiagnostic],
    ) -> None:
        module_qn = _module_qualified_name(relative)
        module_key = entities.symbols.get(module_qn)
        if module_key is None:
            return
        module_entity = entities.entities[module_key]
        local_imports: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(
                    node,
                    request=request,
                    module_entity=module_entity,
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                    local_imports=local_imports,
                )
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_qn = f"{module_qn}.{node.name}"
                instance_types: dict[str, str] = {}
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        instance_types.update(
                            {
                                key: value
                                for key, value in self._collect_local_types(
                                    child,
                                    local_imports=local_imports,
                                    module_qn=module_qn,
                                    class_qn=class_qn,
                                ).items()
                                if key.startswith("self.")
                            }
                        )
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_key = entities.symbols.get(f"{class_qn}.{child.name}")
                        if method_key is None:
                            continue
                        self._walk_calls(
                            child,
                            request=request,
                            caller=entities.entities[method_key],
                            entities=entities,
                            relations=relations,
                            source_id=source_id,
                            observation_id=observation_id,
                            diagnostics=diagnostics,
                            local_imports=local_imports,
                            module_qn=module_qn,
                            class_qn=class_qn,
                            inherited_types=instance_types,
                        )
                # Inheritance after imports are known.
                class_key = entities.symbols.get(class_qn)
                if class_key is None:
                    continue
                cls = entities.entities[class_key]
                for base in node.bases:
                    base_name = _name_of(base)
                    if base_name is None:
                        continue
                    target_qn = local_imports.get(base_name, f"{module_qn}.{base_name}")
                    target_key = entities.symbols.get(target_qn) or entities.symbols.get(
                        base_name
                    )
                    if target_key:
                        self._add_relation(
                            relations,
                            request=request,
                            kind=RelationKind.INHERITS,
                            source=cls,
                            target=entities.entities[target_key],
                            source_id=source_id,
                            observation_id=observation_id,
                            method=ObservationMethod.STATICALLY_RESOLVED,
                            span=SourceSpan(start_line=node.lineno, end_line=node.lineno),
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_key = entities.symbols.get(f"{module_qn}.{node.name}")
                if fn_key is None:
                    continue
                self._walk_calls(
                    node,
                    request=request,
                    caller=entities.entities[fn_key],
                    entities=entities,
                    relations=relations,
                    source_id=source_id,
                    observation_id=observation_id,
                    diagnostics=diagnostics,
                    local_imports=local_imports,
                    module_qn=module_qn,
                    class_qn=None,
                    inherited_types={},
                )

        if relative.startswith("migrations/") and relative.endswith(".py"):
            upgrade = entities.symbols.get(f"{module_qn}.upgrade")
            if upgrade:
                mig = entities.entities[upgrade]
                for _alias, target_qn in local_imports.items():
                    target_key = entities.symbols.get(target_qn)
                    if (
                        target_key
                        and entities.entities[target_key].entity_kind
                        is EntityKind.SCHEMA_OBJECT
                    ):
                        self._add_relation(
                            relations,
                            request=request,
                            kind=RelationKind.MIGRATES,
                            source=mig,
                            target=entities.entities[target_key],
                            source_id=source_id,
                            observation_id=observation_id,
                            method=ObservationMethod.STATICALLY_RESOLVED,
                        )

    def _emit_configures(
        self,
        *,
        request: ExtractionRequest,
        relative: str,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
    ) -> None:
        config_key = None
        for key, entity in entities.entities.items():
            if (
                entity.entity_kind is EntityKind.CONFIGURATION
                and entity.repository_relative_path == relative
            ):
                config_key = key
                break
        if config_key is None:
            return
        config = entities.entities[config_key]
        for entity in entities.entities.values():
            if entity.entity_kind is EntityKind.CLASS and entity.qualified_name and entity.qualified_name.endswith(
                "ItemStore"
            ):
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.CONFIGURES,
                    source=config,
                    target=entity,
                    source_id=source_id,
                    observation_id=observation_id,
                    method=ObservationMethod.STATICALLY_RESOLVED,
                )

    def _emit_class_entities(
        self,
        node: ast.ClassDef,
        *,
        request: ExtractionRequest,
        relative: str,
        module_qn: str,
        module_entity: CodeEntityFact,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
    ) -> None:
        qn = f"{module_qn}.{node.name}"
        span = SourceSpan(start_line=node.lineno, end_line=node.end_lineno or node.lineno)
        cls = self._add_entity(
            entities,
            request=request,
            kind=EntityKind.CLASS,
            path=relative,
            qualified_name=qn,
            source_id=source_id,
            observation_id=observation_id,
            language="python",
            span=span,
        )
        self._add_relation(
            relations,
            request=request,
            kind=RelationKind.DEFINES,
            source=module_entity,
            target=cls,
            source_id=source_id,
            observation_id=observation_id,
            span=SourceSpan(start_line=node.lineno, end_line=node.lineno),
        )
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_qn = f"{qn}.{child.name}"
                method_span = SourceSpan(
                    start_line=child.lineno, end_line=child.end_lineno or child.lineno
                )
                method = self._add_entity(
                    entities,
                    request=request,
                    kind=EntityKind.METHOD,
                    path=relative,
                    qualified_name=method_qn,
                    source_id=source_id,
                    observation_id=observation_id,
                    language="python",
                    span=method_span,
                )
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.DEFINES,
                    source=cls,
                    target=method,
                    source_id=source_id,
                    observation_id=observation_id,
                    span=SourceSpan(start_line=child.lineno, end_line=child.lineno),
                )

    def _emit_function_entity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        request: ExtractionRequest,
        relative: str,
        module_qn: str,
        module_entity: CodeEntityFact,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
    ) -> None:
        qn = f"{module_qn}.{node.name}"
        span = SourceSpan(start_line=node.lineno, end_line=node.end_lineno or node.lineno)
        is_test = relative.startswith("tests/") and node.name.startswith("test_")
        is_api = (relative.endswith("/api.py") or relative == "api.py") and (
            node.name.startswith("handle_") or node.name in {"create_app"}
        )
        if is_test:
            kind = EntityKind.TEST
        elif is_api and node.name.startswith("handle_"):
            kind = EntityKind.API_ENTRY_POINT
        elif relative.startswith("migrations/") and node.name == "upgrade":
            kind = EntityKind.MIGRATION
        else:
            kind = EntityKind.FUNCTION
        fn = self._add_entity(
            entities,
            request=request,
            kind=kind,
            path=relative,
            qualified_name=qn,
            source_id=source_id,
            observation_id=observation_id,
            language="python",
            span=span,
        )
        self._add_relation(
            relations,
            request=request,
            kind=RelationKind.DEFINES,
            source=module_entity,
            target=fn,
            source_id=source_id,
            observation_id=observation_id,
            span=SourceSpan(start_line=node.lineno, end_line=node.lineno),
        )
        if kind is EntityKind.API_ENTRY_POINT:
            self._add_relation(
                relations,
                request=request,
                kind=RelationKind.EXPOSES,
                source=module_entity,
                target=fn,
                source_id=source_id,
                observation_id=observation_id,
                span=SourceSpan(start_line=node.lineno, end_line=node.lineno),
            )

    def _capture_store_path_defaults(
        self,
        node: ast.ClassDef,
        *,
        request: ExtractionRequest,
        class_qn: str,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
    ) -> None:
        default_path: str | None = None
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != "__init__":
                continue
            for arg in child.args.args:
                continue
            # defaults align to trailing args; look for Constant string defaults.
            positional = [a.arg for a in child.args.args if a.arg != "self"]
            defaults = list(child.args.defaults)
            if not defaults:
                continue
            for name, default in zip(positional[-len(defaults) :], defaults, strict=False):
                if isinstance(default, ast.Constant) and isinstance(default.value, str):
                    if "path" in name or default.value.endswith(".json"):
                        default_path = default.value
        if default_path is None:
            return
        file_entity = self._add_entity(
            entities,
            request=request,
            kind=EntityKind.FILE,
            path=default_path,
            qualified_name=default_path,
            source_id=source_id,
            observation_id=observation_id,
            language=None,
        )
        for method_name, kind in (
            ("read_message", RelationKind.READS),
            ("write_message", RelationKind.WRITES),
        ):
            method_key = entities.symbols.get(f"{class_qn}.{method_name}")
            if method_key is None:
                continue
            self._add_relation(
                relations,
                request=request,
                kind=kind,
                source=entities.entities[method_key],
                target=file_entity,
                source_id=source_id,
                observation_id=observation_id,
                method=ObservationMethod.STATICALLY_RESOLVED,
            )

    def _handle_import(
        self,
        node: ast.Import | ast.ImportFrom,
        *,
        request: ExtractionRequest,
        module_entity: CodeEntityFact,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
        local_imports: dict[str, str],
    ) -> None:
        span = SourceSpan(start_line=node.lineno, end_line=node.end_lineno or node.lineno)
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_imports[alias.asname or alias.name.split(".")[0]] = alias.name
                target_key = entities.symbols.get(alias.name)
                if target_key:
                    self._add_relation(
                        relations,
                        request=request,
                        kind=RelationKind.IMPORTS,
                        source=module_entity,
                        target=entities.entities[target_key],
                        source_id=source_id,
                        observation_id=observation_id,
                        method=ObservationMethod.STATICALLY_RESOLVED,
                        span=span,
                    )
            return
        module_name = node.module or ""
        for alias in node.names:
            full = f"{module_name}.{alias.name}" if module_name else alias.name
            local_name = alias.asname or alias.name
            local_imports[local_name] = full
            # Also map the module itself when importing a module package member.
            if module_name:
                local_imports.setdefault(module_name.split(".")[0], module_name)
            target_key = entities.symbols.get(module_name) or entities.symbols.get(full)
            if target_key:
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.IMPORTS,
                    source=module_entity,
                    target=entities.entities[target_key],
                    source_id=source_id,
                    observation_id=observation_id,
                    method=ObservationMethod.STATICALLY_RESOLVED,
                    span=span,
                )

    def _handle_schema_assign(
        self,
        node: ast.Assign,
        *,
        request: ExtractionRequest,
        relative: str,
        module_qn: str,
        module_entity: CodeEntityFact,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
    ) -> None:
        if not isinstance(node.value, ast.Dict):
            return
        for target in node.targets:
            name = _name_of(target)
            if name is None or not name.endswith("_SCHEMA"):
                continue
            qn = f"{module_qn}.{name}"
            span = SourceSpan(start_line=node.lineno, end_line=node.end_lineno or node.lineno)
            schema = self._add_entity(
                entities,
                request=request,
                kind=EntityKind.SCHEMA_OBJECT,
                path=relative,
                qualified_name=qn,
                source_id=source_id,
                observation_id=observation_id,
                language="python",
                span=span,
            )
            self._add_relation(
                relations,
                request=request,
                kind=RelationKind.DEFINES,
                source=module_entity,
                target=schema,
                source_id=source_id,
                observation_id=observation_id,
                span=span,
            )

    def _walk_calls(
        self,
        fn_node: ast.AST,
        *,
        request: ExtractionRequest,
        caller: CodeEntityFact,
        entities: _EntityAcc,
        relations: _RelationAcc,
        source_id: str,
        observation_id: str,
        diagnostics: list[ExtractionDiagnostic],
        local_imports: dict[str, str],
        module_qn: str,
        class_qn: str | None,
        inherited_types: dict[str, str],
    ) -> None:
        # Any globals()[...] use in this function is unresolved dynamic dispatch.
        if any(
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "globals"
            for node in ast.walk(fn_node)
        ):
            diagnostics.append(
                ExtractionDiagnostic(
                    code=UNRESOLVED_DYNAMIC_CALL,
                    message=(
                        f"{caller.qualified_name} uses globals()[...]; "
                        "no CALLS edge emitted for dynamic target"
                    ),
                    repository_relative_path=caller.repository_relative_path,
                )
            )

        type_map = dict(inherited_types)
        type_map.update(
            self._collect_local_types(
                fn_node,
                local_imports=local_imports,
                module_qn=module_qn,
                class_qn=class_qn,
            )
        )

        for node in ast.walk(fn_node):
            if not isinstance(node, ast.Call):
                continue
            span = SourceSpan(
                start_line=getattr(node, "lineno", 1),
                end_line=getattr(node, "end_lineno", None)
                or getattr(node, "lineno", 1),
            )
            # Dynamic: globals()[name]() direct form — diagnostic already recorded.
            if isinstance(node.func, ast.Subscript):
                if (
                    isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == "globals"
                ):
                    continue
            target_qn = self._resolve_call_target(
                node.func,
                local_imports=local_imports,
                module_qn=module_qn,
                class_qn=class_qn,
                type_map=type_map,
                entities=entities,
            )
            if target_qn is None:
                continue
            # Do not emit CALLS to unresolved dynamic handler names.
            if target_qn.endswith(".handler") or target_qn.rsplit(".", 1)[-1] == "handler":
                continue
            target_key = entities.symbols.get(target_qn)
            if target_key is None:
                continue
            target = entities.entities[target_key]
            # Constructor ClassName() is not a CALLS edge in the golden catalog;
            # only emit CALLS to functions/methods/API/test/migration symbols.
            if target.entity_kind is EntityKind.CLASS:
                continue
            # Test callers record TESTS edges; avoid double-counting as CALLS.
            if caller.entity_kind is not EntityKind.TEST:
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.CALLS,
                    source=caller,
                    target=target,
                    source_id=source_id,
                    observation_id=observation_id,
                    method=ObservationMethod.STATICALLY_RESOLVED,
                    span=span,
                )
            # HANDLES: API entry point dispatching to a service/method target,
            # not same-module helper functions like create_app().
            if (
                caller.entity_kind is EntityKind.API_ENTRY_POINT
                and target.entity_kind is EntityKind.METHOD
            ):
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.HANDLES,
                    source=caller,
                    target=target,
                    source_id=source_id,
                    observation_id=observation_id,
                    method=ObservationMethod.STATICALLY_RESOLVED,
                    span=span,
                )
            if caller.entity_kind is EntityKind.TEST and target.entity_kind in {
                EntityKind.FUNCTION,
                EntityKind.METHOD,
                EntityKind.API_ENTRY_POINT,
            }:
                self._add_relation(
                    relations,
                    request=request,
                    kind=RelationKind.TESTS,
                    source=caller,
                    target=target,
                    source_id=source_id,
                    observation_id=observation_id,
                    method=ObservationMethod.STATICALLY_RESOLVED,
                    span=span,
                )
            # Path.read_text / write_text against constant path strings.
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "read_text",
                "write_text",
            }:
                path_const = None
                if (
                    isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == "Path"
                    and node.func.value.args
                    and isinstance(node.func.value.args[0], ast.Constant)
                    and isinstance(node.func.value.args[0].value, str)
                ):
                    path_const = node.func.value.args[0].value
                if path_const:
                    file_entity = self._add_entity(
                        entities,
                        request=request,
                        kind=EntityKind.FILE,
                        path=path_const,
                        qualified_name=path_const,
                        source_id=source_id,
                        observation_id=observation_id,
                        language=None,
                    )
                    self._add_relation(
                        relations,
                        request=request,
                        kind=(
                            RelationKind.READS
                            if node.func.attr == "read_text"
                            else RelationKind.WRITES
                        ),
                        source=caller,
                        target=file_entity,
                        source_id=source_id,
                        observation_id=observation_id,
                        method=ObservationMethod.STATICALLY_RESOLVED,
                        span=span,
                    )

    def _collect_local_types(
        self,
        fn_node: ast.AST,
        *,
        local_imports: dict[str, str],
        module_qn: str,
        class_qn: str | None,
    ) -> dict[str, str]:
        """Map local names / self.attrs to class qualified names when unambiguous."""

        types: dict[str, str] = {}

        def resolve_class_ref(node: ast.AST) -> str | None:
            name = _name_of(node)
            if name is None:
                return None
            if name in local_imports:
                return local_imports[name]
            # Annotation forms like ItemStore | None → take first Name.
            return f"{module_qn}.{name}" if "." not in name else name

        def class_from_ctor(node: ast.AST) -> str | None:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                return resolve_class_ref(node.func)
            if isinstance(node, ast.BoolOp):
                for value in node.values:
                    found = class_from_ctor(value)
                    if found is not None:
                        return found
            return None

        # Parameter annotations: store: ItemStore | None
        if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in fn_node.args.args:
                if arg.arg == "self" or arg.annotation is None:
                    continue
                # Walk annotation Names; prefer imported class names.
                for child in ast.walk(arg.annotation):
                    if isinstance(child, ast.Name) and child.id in local_imports:
                        types[arg.arg] = local_imports[child.id]
                        break

        for node in ast.walk(fn_node):
            if isinstance(node, ast.Assign):
                class_qn_found = class_from_ctor(node.value)
                if class_qn_found is None:
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        types[target.id] = class_qn_found
                    elif (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        types[f"self.{target.attr}"] = class_qn_found
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                class_qn_found = class_from_ctor(node.value)
                if class_qn_found is None and node.annotation is not None:
                    for child in ast.walk(node.annotation):
                        if isinstance(child, ast.Name) and child.id in local_imports:
                            class_qn_found = local_imports[child.id]
                            break
                if class_qn_found is None:
                    continue
                target = node.target
                if isinstance(target, ast.Name):
                    types[target.id] = class_qn_found
                elif (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    types[f"self.{target.attr}"] = class_qn_found
            elif isinstance(node, ast.Assert) and isinstance(node.test, ast.Call):
                # assert isinstance(greeter, Greeter)
                call = node.test
                if (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "isinstance"
                    and len(call.args) == 2
                    and isinstance(call.args[0], ast.Name)
                ):
                    class_ref = resolve_class_ref(call.args[1])
                    if class_ref is not None:
                        types[call.args[0].id] = class_ref
        return types

    def _resolve_call_target(
        self,
        func: ast.AST,
        *,
        local_imports: dict[str, str],
        module_qn: str,
        class_qn: str | None,
        type_map: dict[str, str],
        entities: _EntityAcc,
    ) -> str | None:
        if isinstance(func, ast.Name):
            imported = local_imports.get(func.id)
            if imported:
                return imported
            return f"{module_qn}.{func.id}"
        if isinstance(func, ast.Attribute):
            # Greeter().greet(...) — constructor receiver is unambiguous.
            if isinstance(func.value, ast.Call) and isinstance(func.value.func, ast.Name):
                class_ref = local_imports.get(func.value.func.id)
                if class_ref is None:
                    class_ref = f"{module_qn}.{func.value.func.id}"
                return f"{class_ref}.{func.attr}"
            # self._store.write_message / greeter.greet with known types
            if isinstance(func.value, ast.Attribute) and isinstance(
                func.value.value, ast.Name
            ):
                if func.value.value.id == "self":
                    typed = type_map.get(f"self.{func.value.attr}")
                    if typed is not None:
                        return f"{typed}.{func.attr}"
            if isinstance(func.value, ast.Name):
                if func.value.id == "self" and class_qn:
                    return f"{class_qn}.{func.attr}"
                typed = type_map.get(func.value.id)
                if typed is not None:
                    candidate = f"{typed}.{func.attr}"
                    if candidate in entities.symbols:
                        return candidate
                imported = local_imports.get(func.value.id)
                if imported:
                    return f"{imported}.{func.attr}"
                return f"{module_qn}.{func.value.id}.{func.attr}"
        return None


def _module_qualified_name(relative: str) -> str:
    path = Path(relative)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name_of(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None
