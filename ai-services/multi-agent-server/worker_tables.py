"""Render explicitly requested Markdown tables from model-authored cells and references."""

import re

MIN_COLUMNS, MAX_COLUMNS = 2, 10
MAX_ROWS, MAX_CELL_CHARS = 20, 500
CITATION_COLUMNS = {"evidence", "citation", "citations", "sources"}


def _citation_index(columns):
    if not isinstance(columns, list) or not MIN_COLUMNS <= len(columns) <= MAX_COLUMNS:
        raise ValueError("Requested tables need 2-10 columns.")
    if any(not isinstance(column, str) or not column.strip() for column in columns):
        raise ValueError("Requested table headings must be nonempty strings.")
    matches = [i for i, column in enumerate(columns) if column.strip().casefold() in CITATION_COLUMNS]
    if len(matches) != 1:
        raise ValueError("Requested tables need exactly one citation column.")
    return matches[0]


def requested_columns(task):
    """Recognise one unambiguous, explicit Markdown header and separator example."""
    if not isinstance(task, str):
        return None
    candidates = []
    lines = task.splitlines()
    for heading, divider in zip(lines, lines[1:]):
        heading, divider = heading.strip(), divider.strip()
        if not all(line.startswith("|") and line.endswith("|") for line in (heading, divider)):
            continue
        columns = [cell.strip() for cell in heading[1:-1].split("|")]
        separators = [cell.strip() for cell in divider[1:-1].split("|")]
        if len(columns) != len(separators) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separators):
            continue
        try:
            _citation_index(columns)
        except ValueError:
            continue
        candidates.append(columns)
    return candidates[0] if candidates and all(value == candidates[0] for value in candidates) else None


def response_schema(columns, allowed):
    """Build a table schema using usable E IDs, never source IDs or guessed mappings."""
    _citation_index(columns)
    if not isinstance(allowed, list) or not allowed or any(
            not isinstance(item, str) or not re.fullmatch(r"E\d+", item) for item in allowed):
        raise ValueError("Table citations need usable E IDs.")
    row = {
        "type": "object",
        "properties": {
            "cells": {"type": "array", "items": {"type": "string", "maxLength": MAX_CELL_CHARS},
                      "minItems": len(columns) - 1, "maxItems": len(columns) - 1},
            "citation": {"type": "string", "enum": [f"[{item}]" for item in allowed]},
        },
        "required": ["cells", "citation"], "additionalProperties": False,
    }
    return {"type": "object", "properties": {"rows": {
        "type": "array", "items": row, "minItems": 1, "maxItems": MAX_ROWS,
    }}, "required": ["rows"], "additionalProperties": False}


def _markdown_cell(value):
    # Preserve literal slashes/pipes and line boundaries inside one table cell.
    return (value.replace("\\", "\\\\").replace("|", r"\|")
            .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>"))


def decode_table(value, columns, schema):
    """Validate every model field before formatting; never return a partial table."""
    try:
        citation_index = _citation_index(columns)
        row_schema = schema["properties"]["rows"]["items"]["properties"]
        permitted = row_schema["citation"]["enum"]
    except (KeyError, TypeError, ValueError):
        return "", ["The requested table schema is invalid."]
    if not isinstance(permitted, list) or not permitted or any(
            not isinstance(item, str) or not re.fullmatch(r"\[E\d+\]", item) for item in permitted):
        return "", ["The requested table schema has no usable citation choices."]
    if not isinstance(value, dict) or set(value) != {"rows"} or not isinstance(value["rows"], list):
        return "", ["Return exactly one rows array in the table object."]
    if not 1 <= len(value["rows"]) <= MAX_ROWS:
        return "", [f"Return between 1 and {MAX_ROWS} table rows."]
    rendered = []
    for row in value["rows"]:
        if not isinstance(row, dict) or set(row) != {"cells", "citation"}:
            return "", ["Every table row must contain exactly cells and citation."]
        cells = row["cells"]
        if not isinstance(cells, list) or len(cells) != len(columns) - 1 or any(
                not isinstance(cell, str) or len(cell) > MAX_CELL_CHARS for cell in cells):
            return "", [f"Each row needs {len(columns) - 1} text cells of at most {MAX_CELL_CHARS} characters."]
        if not isinstance(row["citation"], str) or row["citation"] not in permitted:
            return "", ["Every table row must select one complete permitted [E#] citation."]
        output = [_markdown_cell(cell) for cell in cells]
        output.insert(citation_index, row["citation"])
        rendered.append("| " + " | ".join(output) + " |")
    headings = "| " + " | ".join(_markdown_cell(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    return "\n".join([headings, separator, *rendered]), []
