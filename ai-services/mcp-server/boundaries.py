"""Tool boundaries for the shared MCP server.

Release 1 requires the MCP server to "enforce defined tool boundaries". A tool
boundary here is not a comment in a docstring - it is a rule this module
applies before any request leaves the process, so a tool that tries to step
outside its declared reach fails loudly instead of quietly succeeding.

Four boundaries are enforced on every tool call:

  1. Read-only     - only GET is ever issued upstream. No MCP tool can write.
  2. Allowlisted   - the target host:port must be the one the tool declared.
  3. Schema-checked- arguments must match the tool's declared input schema.
  4. Capped        - results are truncated to the tool's row limit, and every
                     upstream call has a timeout.

The MCP server runs on the host, not in Docker, so upstream targets are
localhost ports published by docker-compose rather than compose DNS names.
"""

import os

import requests


class BoundaryError(Exception):
    """Raised when a tool call would cross a declared boundary."""

    def __init__(self, message, boundary):
        super().__init__(message)
        self.boundary = boundary


# Every host:port an MCP tool is permitted to read from. A tool may only name a
# target that appears here; anything else is refused before a socket is opened.
ALLOWED_TARGETS = {
    "student-1-db": os.getenv("STUDENT_1_DB_URL", "http://localhost:5201"),
    "student-2-db": os.getenv("STUDENT_2_DB_URL", "http://localhost:5202"),
    "student-3-db": os.getenv("STUDENT_3_DB_URL", "http://localhost:5203"),
    "student-4-db": os.getenv("STUDENT_4_DB_URL", "http://localhost:5204"),
    "student-5-db": os.getenv("STUDENT_5_DB_URL", "http://localhost:5205"),
    "shared-db": os.getenv("SHARED_DB_URL", "http://localhost:5200"),
}

UPSTREAM_TIMEOUT = float(os.getenv("MCP_UPSTREAM_TIMEOUT", "8"))


def validate_arguments(schema, arguments):
    """Check arguments against a tool's declared input schema.

    A deliberately small validator rather than a jsonschema dependency: the
    schemas are flat, and keeping it here means the rule being enforced is
    readable next to the rule being declared.
    """
    arguments = arguments or {}

    unexpected = set(arguments) - set(schema.get("properties", {}))
    if unexpected:
        raise BoundaryError(
            f"unexpected argument(s): {', '.join(sorted(unexpected))}",
            "schema-checked",
        )

    for name in schema.get("required", []):
        if arguments.get(name) in (None, ""):
            raise BoundaryError(f"missing required argument: {name}", "schema-checked")

    cleaned = {}
    for name, value in arguments.items():
        spec = schema["properties"][name]
        expected = spec.get("type", "string")

        if expected == "integer":
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise BoundaryError(f"argument '{name}' must be an integer", "schema-checked")
            if "minimum" in spec and value < spec["minimum"]:
                raise BoundaryError(
                    f"argument '{name}' must be >= {spec['minimum']}", "schema-checked"
                )
            if "maximum" in spec and value > spec["maximum"]:
                raise BoundaryError(
                    f"argument '{name}' must be <= {spec['maximum']}", "schema-checked"
                )
        else:
            value = str(value).strip()
            if "enum" in spec and value not in spec["enum"]:
                raise BoundaryError(
                    f"argument '{name}' must be one of: {', '.join(spec['enum'])}",
                    "schema-checked",
                )
            if len(value) > spec.get("maxLength", 200):
                raise BoundaryError(
                    f"argument '{name}' exceeds {spec.get('maxLength', 200)} characters",
                    "schema-checked",
                )

        cleaned[name] = value

    return cleaned


def read(target, path, params=None):
    """Issue the one kind of upstream call a tool is allowed to make: a GET.

    There is no matching write() by design. Boundary 1 is enforced by this
    module offering no way to do anything else.
    """
    if target not in ALLOWED_TARGETS:
        raise BoundaryError(f"'{target}' is not an allowlisted MCP target", "allowlisted")

    base = ALLOWED_TARGETS[target]
    try:
        response = requests.get(
            f"{base}{path}", params=params or {}, timeout=UPSTREAM_TIMEOUT
        )
    except requests.RequestException as exc:
        raise BoundaryError(f"{target} is unreachable at {base}: {exc}", "availability")

    if response.status_code != 200:
        raise BoundaryError(
            f"{target} returned HTTP {response.status_code} for {path}", "upstream"
        )

    try:
        return response.json()
    except ValueError:
        raise BoundaryError(f"{target} returned a non-JSON body for {path}", "upstream")


def cap(rows, limit):
    """Boundary 4: never hand the caller an unbounded result set."""
    if not isinstance(rows, list):
        return rows, False
    return rows[:limit], len(rows) > limit
