"""Requested tables keep model-authored cells and exact model-selected citations."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest


SERVICE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("worker_table_test_module", SERVICE / "worker_tables.py")
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)
COLUMNS = ["Item", "Region", "Recorded hours", "Reason", "Evidence"]
ALLOWED = ["E1", "E3"]
SCHEMA = tables.response_schema(COLUMNS, ALLOWED)
VALID_ROW = {"cells": ["Example A", "North", "09:00-17:00", "A recorded reason."], "citation": "[E3]"}


def example(columns):
    return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |"


@pytest.mark.parametrize("reference", ["Evidence", "evidence", "Citation", "CITATIONS", "Sources"])
def test_requested_columns_are_generic_and_preserve_the_requested_labels(reference):
    columns = ["Recorded item", reference, "Explanation"]
    assert tables.requested_columns("Follow the requested format:\n" + example(columns)) == columns


def test_requested_columns_support_aligned_separators_and_indented_examples():
    task = "Table:\n  | Item | Citations | Value |\n  | :--- | :---: | ---: |\nFinish."
    assert tables.requested_columns(task) == ["Item", "Citations", "Value"]


@pytest.mark.parametrize("task", [
    None, 3, "Write a table.", "Item | Evidence\n--- | ---", "| Item | Evidence |",
    "| Item | Evidence |\n| --- |",
    "| Item | Evidence |\n| --- | -- |",
    "| Item | Value |\n| --- | --- |",
    "| Evidence |\n| --- |",
    "| Item | Evidence | Sources |\n| --- | --- | --- |",
    "| | Evidence |\n| --- | --- |",
    example(["Item"] * 10 + ["Evidence"]),
])
def test_unrequested_ambiguous_or_malformed_tables_do_not_enable_table_mode(task):
    assert tables.requested_columns(task) is None


def test_different_table_examples_are_ambiguous_but_identical_repetition_is_safe():
    first = example(["Item", "Evidence"])
    assert tables.requested_columns(first + "\n" + example(["Result", "Citation"])) is None
    assert tables.requested_columns(first + "\n" + first) == ["Item", "Evidence"]


def test_schema_has_exact_requested_cell_count_and_only_usable_complete_references():
    schema = tables.response_schema(COLUMNS, ALLOWED)
    assert schema["required"] == ["rows"] and schema["additionalProperties"] is False
    rows = schema["properties"]["rows"]
    assert rows["minItems"] == 1 and rows["maxItems"] == 20
    row = rows["items"]
    assert set(row["required"]) == {"cells", "citation"}
    assert row["additionalProperties"] is False
    assert row["properties"]["citation"]["enum"] == ["[E1]", "[E3]"]
    cells = row["properties"]["cells"]
    assert cells["minItems"] == cells["maxItems"] == 4
    assert cells["items"] == {"type": "string", "maxLength": 500}
    assert "pattern" not in json.dumps(schema)


@pytest.mark.parametrize("columns,allowed", [
    (["Item"], ALLOWED), (["Item", "Value"], ALLOWED),
    (["Evidence", "Sources"], ALLOWED), (["Item", "Evidence"], []),
    (["Item", "Evidence"], ["S1"]), (["Item", "Evidence"], ["[E1]"]),
    (["Item", "Evidence"], [1]), (["Item", "Evidence"], None),
])
def test_invalid_schema_inputs_are_rejected_instead_of_guessing_a_mapping(columns, allowed):
    with pytest.raises(ValueError):
        tables.response_schema(columns, allowed)


def test_eight_model_authored_rows_are_all_preserved_in_order_without_invented_facts():
    rows = [{"cells": [f"Record {i}", "Region supplied by model", f"{i:02}:00-{i+1:02}:00",
                        f"The model's recorded explanation {i}."],
             "citation": "[E1]" if i % 2 else "[E3]"} for i in range(1, 9)]
    source = {"rows": rows}
    unchanged = copy.deepcopy(source)
    markdown, issues = tables.decode_table(source, COLUMNS, SCHEMA)
    assert issues == [] and source == unchanged
    lines = markdown.splitlines()
    assert len(lines) == 10
    assert lines[:2] == example(COLUMNS).splitlines()
    for number, row in enumerate(rows, start=2):
        assert lines[number] == "| " + " | ".join([*row["cells"], row["citation"]]) + " |"
    assert "Unknown" not in markdown


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_model_selected_citation_is_placed_in_the_requested_column(index):
    columns = ["Name", "Value", "Reason"]
    columns.insert(index, "Citation")
    schema = tables.response_schema(columns, ["E7"])
    markdown, issues = tables.decode_table({"rows": [{"cells": ["A", "B", "C"], "citation": "[E7]"}]},
                                          columns, schema)
    assert issues == []
    expected = ["A", "B", "C"]
    expected.insert(index, "[E7]")
    assert markdown.splitlines()[-1] == "| " + " | ".join(expected) + " |"


@pytest.mark.parametrize("invalid", [
    None, [], "rows", {}, {"rows": []}, {"rows": {}},
    {"rows": [VALID_ROW], "extra": "ignored data"},
    {"rows": [None]}, {"rows": [[]]},
    {"rows": [{"cells": VALID_ROW["cells"]}]},
    {"rows": [{**VALID_ROW, "extra": "ignored data"}]},
    {"rows": [{"cells": "not a list", "citation": "[E1]"}]},
    {"rows": [{"cells": ["a", "b", "c"], "citation": "[E1]"}]},
    {"rows": [{"cells": ["a", "b", "c", "d", "e"], "citation": "[E1]"}]},
    {"rows": [{"cells": ["a", "b", None, "d"], "citation": "[E1]"}]},
    {"rows": [{"cells": ["a", "b", 7, "d"], "citation": "[E1]"}]},
    {"rows": [{"cells": ["a", "b", {"nested": "data"}, "d"], "citation": "[E1]"}]},
    {"rows": [{"cells": ["a" * 501, "b", "c", "d"], "citation": "[E1]"}]},
    {"rows": [VALID_ROW] * 21},
])
def test_invalid_or_extra_model_data_fails_closed_without_a_partial_table(invalid):
    markdown, issues = tables.decode_table(invalid, COLUMNS, SCHEMA)
    assert markdown == "" and issues


@pytest.mark.parametrize("citation", ["[E2]", "[E99]", "E1", "[S1]", "[e1]", "[E1, E3]", None, ["[E1]"]])
def test_unavailable_unknown_or_malformed_citations_are_never_appended_or_remapped(citation):
    row = {**VALID_ROW, "citation": citation}
    markdown, issues = tables.decode_table({"rows": [row]}, COLUMNS, SCHEMA)
    assert markdown == "" and issues


def test_failure_in_one_row_does_not_silently_drop_it_or_return_the_other_rows():
    invalid = {"rows": [VALID_ROW, {**VALID_ROW, "citation": "[E99]"}, VALID_ROW]}
    markdown, issues = tables.decode_table(invalid, COLUMNS, SCHEMA)
    assert markdown == "" and issues


def test_markdown_escaping_preserves_literal_pipes_backslashes_and_line_boundaries():
    cell = 'A | B\\path\nNext line\r\nFinal line\rEnd'
    row = {"cells": [cell, '"Quoted" item', "  keep spaces  ", "Reason [E1]."], "citation": "[E3]"}
    markdown, issues = tables.decode_table({"rows": [row]}, COLUMNS, SCHEMA)
    assert issues == []
    assert 'A \\| B\\\\path<br>Next line<br>Final line<br>End' in markdown
    assert '"Quoted" item' in markdown
    assert "  keep spaces  " in markdown
    assert "Reason [E1]." in markdown
    assert len(markdown.splitlines()) == 3


def test_existing_citations_in_text_are_preserved_for_the_callers_existing_validation():
    row = {"cells": ["An incorrect claim [E99]", "B", "C", "D"], "citation": "[E1]"}
    markdown, issues = tables.decode_table({"rows": [row]}, COLUMNS, SCHEMA)
    assert issues == []
    assert "[E99]" in markdown and "[E1]" in markdown


@pytest.mark.parametrize("schema", [None, {}, {"properties": {}}, {"properties": {"rows": {"items": {"properties": {"citation": {"enum": None}}}}}}])
def test_invalid_internal_schema_fails_with_a_clear_issue(schema):
    markdown, issues = tables.decode_table({"rows": [VALID_ROW]}, COLUMNS, schema)
    assert markdown == "" and issues
