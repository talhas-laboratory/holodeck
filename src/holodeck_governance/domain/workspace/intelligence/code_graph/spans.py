"""Source span contracts for factual code-graph evidence."""

from __future__ import annotations

from dataclasses import dataclass

from holodeck_governance.domain.workspace.intelligence.code_graph.types import (
    CodeGraphReason,
    code_graph_error,
)


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """1-indexed inclusive source span within a repository-relative file."""

    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < 1:
            raise code_graph_error(
                CodeGraphReason.INVALID_SPAN, "span lines must be >= 1"
            )
        if self.end_line < self.start_line:
            raise code_graph_error(
                CodeGraphReason.INVALID_SPAN,
                "end_line must be greater than or equal to start_line",
            )
        columns = (self.start_column, self.end_column)
        if any(column is None for column in columns) and any(
            column is not None for column in columns
        ):
            raise code_graph_error(
                CodeGraphReason.INVALID_SPAN,
                "start_column and end_column must both be set or both omitted",
            )
        if self.start_column is not None and self.end_column is not None:
            if self.start_column < 1 or self.end_column < 1:
                raise code_graph_error(
                    CodeGraphReason.INVALID_SPAN, "span columns must be >= 1"
                )
            if (
                self.start_line == self.end_line
                and self.end_column < self.start_column
            ):
                raise code_graph_error(
                    CodeGraphReason.INVALID_SPAN,
                    "end_column must be greater than or equal to start_column "
                    "on the same line",
                )
