from __future__ import annotations

from holodeck_runtime.errors import ValidationError

MAX_STRING_LIST_ITEMS = 256
MAX_STRING_LIST_ITEM_LENGTH = 1024
MAX_STRING_LIST_TOTAL_LENGTH = 32_768
MAX_CLAIMED_PATHS = 64
MAX_TITLE_LENGTH = 256
MAX_SHORT_TEXT_LENGTH = 128
MAX_TEXT_FIELD_LENGTH = 4096


def validate_text_field(
    name: str,
    value: object,
    *,
    max_length: int = MAX_TEXT_FIELD_LENGTH,
    required: bool = False,
    default: str = "",
) -> str:
    if value is None:
        if required:
            raise ValidationError(f"{name} is required")
        return default
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    text = value.strip()
    if required and not text:
        raise ValidationError(f"{name} is required")
    if len(text) > max_length:
        raise ValidationError(f"{name} exceeds maximum length of {max_length}")
    return text


def validate_string_list(
    name: str,
    value: object,
    *,
    max_items: int = MAX_STRING_LIST_ITEMS,
    max_item_length: int = MAX_STRING_LIST_ITEM_LENGTH,
    max_total_length: int = MAX_STRING_LIST_TOTAL_LENGTH,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise ValidationError(f"{name} must be a list, not a string")
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be a list")
    if len(value) > max_items:
        raise ValidationError(f"{name} exceeds maximum of {max_items} items")

    result: list[str] = []
    total_length = 0
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"{name} items must be strings")
        text = item.strip()
        if not text:
            continue
        if len(text) > max_item_length:
            raise ValidationError(f"{name} item exceeds maximum length of {max_item_length}")
        total_length += len(text)
        if total_length > max_total_length:
            raise ValidationError(f"{name} exceeds maximum total length of {max_total_length}")
        result.append(text)
    return result
