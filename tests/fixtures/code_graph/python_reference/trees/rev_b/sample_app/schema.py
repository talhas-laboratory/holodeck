"""Logical schema objects for the sample application."""

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
    },
    "required": ["message"],
}
