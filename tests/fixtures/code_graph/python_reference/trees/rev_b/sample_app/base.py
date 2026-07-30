"""Base types for the sample application."""


class Animal:
    """Root type used to demonstrate inheritance facts."""

    kind = "animal"

    def label(self) -> str:
        return self.kind
