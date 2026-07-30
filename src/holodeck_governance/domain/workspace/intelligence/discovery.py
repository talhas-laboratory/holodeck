"""Conservative repository/source discovery and trust classification (M2-014).

Invent WorkspaceSource *candidates* from bound-repo path observations. Discovery
never grants instruction_authority or authoritative_reference; those require
explicit curator promotion later (M2-015).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from holodeck_governance.domain.errors import MalformedCommandError
from holodeck_governance.domain.workspace.intelligence.types import (
    SourceType,
    TrustClass,
)

# Discovery is deliberately conservative: these trust classes are never invented.
_FORBIDDEN_DISCOVERY_TRUST: frozenset[TrustClass] = frozenset(
    {
        TrustClass.INSTRUCTION_AUTHORITY,
        TrustClass.AUTHORITATIVE_REFERENCE,
        TrustClass.GENERATED_INTERPRETATION,
    }
)

_DEFAULT_SENSITIVITY = "public"
_DEFAULT_REFRESH_POLICY = "on_revision_change"

_MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "pipfile.lock",
        "composer.json",
        "gemfile",
        "gemfile.lock",
        "makefile",
        "dockerfile",
        "containerfile",
    }
)

_SOURCE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".cs",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".scala",
    }
)

_DOC_SUFFIXES: frozenset[str] = frozenset(
    {".md", ".mdx", ".rst", ".adoc", ".txt"}
)

_DOC_BASENAMES: frozenset[str] = frozenset(
    {
        "readme",
        "changelog",
        "changes",
        "contributing",
        "authors",
        "license",
        "copying",
        "notice",
        "security",
        "code_of_conduct",
    }
)


@dataclass(frozen=True, slots=True)
class ObservedSourcePath:
    """A path/locator observed from a bound repository inventory."""

    locator: str
    observed_revision: str
    kind_hint: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.locator.strip():
            raise MalformedCommandError("locator is required")
        if not self.observed_revision.strip():
            raise MalformedCommandError("observed_revision is required")
        if self.kind_hint is not None and not self.kind_hint.strip():
            raise MalformedCommandError("kind_hint must be non-empty when set")
        if self.content_hash is not None and not self.content_hash.strip():
            raise MalformedCommandError("content_hash must be non-empty when set")


@dataclass(frozen=True, slots=True)
class DiscoveredSourceCandidate:
    """Classification result ready to become a WorkspaceSource.

    ``instruction_authority`` is intentionally absent: discovery alone never
    invents instruction authority.
    """

    source_type: SourceType
    locator: str
    observed_revision: str
    trust_class: TrustClass
    sensitivity: str = _DEFAULT_SENSITIVITY
    refresh_policy: str = _DEFAULT_REFRESH_POLICY
    module_tags: tuple[str, ...] = ()
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.locator.strip():
            raise MalformedCommandError("locator is required")
        if not self.observed_revision.strip():
            raise MalformedCommandError("observed_revision is required")
        if not self.sensitivity.strip():
            raise MalformedCommandError("sensitivity is required")
        if not self.refresh_policy.strip():
            raise MalformedCommandError("refresh_policy is required")
        if self.trust_class in _FORBIDDEN_DISCOVERY_TRUST:
            raise MalformedCommandError(
                "discovery cannot invent instruction_authority, "
                "authoritative_reference, or generated_interpretation"
            )
        if self.source_type is SourceType.GENERATED_INTERPRETATION:
            raise MalformedCommandError(
                "discovery cannot invent generated_interpretation sources"
            )
        if self.content_hash is not None and not self.content_hash.strip():
            raise MalformedCommandError("content_hash must be non-empty when set")
        for tag in self.module_tags:
            if not tag.strip():
                raise MalformedCommandError("module_tags entries must be non-empty")


def observed_path_for_classification(locator: str) -> str:
    """Normalize a locator to a lowercase POSIX-ish path for heuristics."""

    text = locator.strip().replace("\\", "/")
    if "://" in text:
        text = text.split("://", 1)[1]
    if "#" in text:
        text = text.split("#", 1)[-1]
    # Drop optional host/repo prefix when locator looks like host/repo/path
    # (e.g. github.com/org/repo/README.md). Do not treat dotfiles like .github
    # as hostnames.
    parts = [p for p in text.split("/") if p]
    if (
        len(parts) >= 3
        and "." in parts[0]
        and not parts[0].startswith(".")
        and "/" not in parts[0]
    ):
        text = "/".join(parts[2:])
    return text.lstrip("/").lower()


def classify_observed_path(
    observation: ObservedSourcePath,
) -> DiscoveredSourceCandidate:
    """Deterministic, conservative classification from path patterns / kind hint."""

    path = observed_path_for_classification(observation.locator)
    hint = (observation.kind_hint or "").strip().lower()
    posix = PurePosixPath(path)
    name = posix.name
    stem = posix.stem.lower()
    suffix = posix.suffix.lower()
    parts = posix.parts

    source_type, trust, tags = _classify(
        path=path,
        hint=hint,
        name=name,
        stem=stem,
        suffix=suffix,
        parts=parts,
    )
    return DiscoveredSourceCandidate(
        source_type=source_type,
        locator=observation.locator.strip(),
        observed_revision=observation.observed_revision.strip(),
        trust_class=trust,
        sensitivity=_DEFAULT_SENSITIVITY,
        refresh_policy=_DEFAULT_REFRESH_POLICY,
        module_tags=tags,
        content_hash=observation.content_hash,
    )


def invent_sources_from_observations(
    observations: tuple[ObservedSourcePath, ...] | list[ObservedSourcePath],
) -> tuple[DiscoveredSourceCandidate, ...]:
    """Invent source candidates from observations; dedupe by locator (first wins)."""

    seen: set[str] = set()
    out: list[DiscoveredSourceCandidate] = []
    for observation in observations:
        candidate = classify_observed_path(observation)
        if candidate.locator in seen:
            continue
        seen.add(candidate.locator)
        out.append(candidate)
    return tuple(out)


def _classify(
    *,
    path: str,
    hint: str,
    name: str,
    stem: str,
    suffix: str,
    parts: tuple[str, ...],
) -> tuple[SourceType, TrustClass, tuple[str, ...]]:
    if hint in {"ci", "github_actions", "pipeline", "workflow"} or _is_ci_path(
        path, parts, name
    ):
        return (
            SourceType.REPOSITORY_FILE,
            TrustClass.TRUSTED_OBSERVATION,
            ("operations-and-release",),
        )

    if hint in {"test", "tests", "test_result"} or _is_test_path(
        path, parts, name, stem, suffix
    ):
        return (
            SourceType.TEST_RESULT,
            TrustClass.ORDINARY_REFERENCE,
            ("testing-and-verification",),
        )

    if hint in {"document", "docs", "readme"} or _is_document_path(
        path, parts, name, stem, suffix
    ):
        tags = ("security-and-authority",) if stem == "security" else ("product-and-users",)
        if "architecture" in path or stem in {"architecture", "adr"}:
            tags = ("architecture",)
        return SourceType.DOCUMENT, TrustClass.ORDINARY_REFERENCE, tags

    if hint in {"manifest", "lockfile", "dependency"} or name in _MANIFEST_NAMES:
        return (
            SourceType.REPOSITORY_FILE,
            TrustClass.ORDINARY_REFERENCE,
            ("architecture", "operations-and-release"),
        )

    if hint in {"source", "code", "repository_file"} or _is_source_path(
        path, parts, suffix
    ):
        return (
            SourceType.REPOSITORY_FILE,
            TrustClass.UNTRUSTED_REFERENCE,
            ("architecture",),
        )

    # Unknown path: still invent a repository file, but keep trust low.
    return (
        SourceType.REPOSITORY_FILE,
        TrustClass.UNTRUSTED_REFERENCE,
        ("architecture",),
    )


def _is_ci_path(path: str, parts: tuple[str, ...], name: str) -> bool:
    if parts and parts[0] in {".github", ".gitlab", ".circleci", ".buildkite"}:
        return True
    if "ci/" in path or path.startswith("ci/") or "/.github/" in f"/{path}":
        return True
    return name in {
        "jenkinsfile",
        ".gitlab-ci.yml",
        ".travis.yml",
        "azure-pipelines.yml",
    }


def _is_test_path(
    path: str,
    parts: tuple[str, ...],
    name: str,
    stem: str,
    suffix: str,
) -> bool:
    if any(part in {"tests", "test", "__tests__", "spec"} for part in parts):
        return True
    if stem.startswith("test_") or stem.endswith("_test") or stem.endswith(".test"):
        return True
    if stem.endswith(".spec") or name.endswith(".spec.ts") or name.endswith(".test.js"):
        return True
    if suffix in {".spec.ts", ".spec.js", ".test.ts", ".test.js"}:
        return True
    return False


def _is_document_path(
    path: str,
    parts: tuple[str, ...],
    name: str,
    stem: str,
    suffix: str,
) -> bool:
    if parts and parts[0] in {"docs", "doc", "documentation"}:
        return True
    if stem in _DOC_BASENAMES or stem.startswith("readme"):
        return True
    if suffix in _DOC_SUFFIXES and (
        stem in _DOC_BASENAMES or "docs/" in path or path.startswith("docs/")
    ):
        return True
    if name.lower().startswith("readme"):
        return True
    return False


def _is_source_path(path: str, parts: tuple[str, ...], suffix: str) -> bool:
    if suffix in _SOURCE_SUFFIXES:
        return True
    if parts and parts[0] in {"src", "lib", "app", "pkg", "internal", "cmd"}:
        return True
    return False
