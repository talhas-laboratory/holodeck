"""Initial migration applying the item schema."""

from sample_app.schema import ITEM_SCHEMA


def upgrade() -> dict[str, object]:
    return {"schema": ITEM_SCHEMA, "version": 1}
