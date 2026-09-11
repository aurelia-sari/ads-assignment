"""Registered tools for the shared MCP server.

Every student feature calls this one registry. A tool is a declaration plus a
handler: the declaration is what `tools/list` returns to a client and what the
boundary layer enforces, and the handler is the only code allowed to act on it.

Each tool names exactly one upstream target. That is what keeps the Release 0
service-boundary rule intact - the MCP server does not open anyone's SQLite
file, it reads the owning database service over HTTP, the same as any other
caller would.
"""

import boundaries

REGISTRY = {}


def register(name, description, owner, target, input_schema, row_limit=20):
    """Declare a tool. The decorated function becomes its handler."""

    def decorator(handler):
        REGISTRY[name] = {
            "name": name,
            "description": description,
            "owner": owner,
            "target": target,
            "inputSchema": {"type": "object", **input_schema},
            "rowLimit": row_limit,
            "handler": handler,
        }
        return handler

    return decorator


def describe():
    """The tool list a client sees. Handlers are not serialisable, so drop them."""
    return [
        {key: value for key, value in tool.items() if key != "handler"}
        for tool in sorted(REGISTRY.values(), key=lambda t: t["name"])
    ]


def call(name, arguments):
    """Run one tool through its declared boundaries and return a structured result."""
    tool = REGISTRY.get(name)
    if tool is None:
        raise boundaries.BoundaryError(f"no registered tool named '{name}'", "registered")

    cleaned = boundaries.validate_arguments(tool["inputSchema"], arguments)
    rows, truncated = tool["handler"](cleaned, tool)

    return {
        "tool": name,
        "owner": tool["owner"],
        "source": tool["target"],
        "arguments": cleaned,
        "rows": rows,
        "row_count": len(rows) if isinstance(rows, list) else 1,
        "truncated": truncated,
    }


# --- Student 1 : Trips & Itinerary -----------------------------------------

@register(
    "list_trips",
    "List planned trips, optionally filtered by destination or status.",
    owner="student-1",
    target="student-1-db",
    input_schema={
        "properties": {
            "destination": {"type": "string", "maxLength": 60,
                            "description": "Partial destination name, e.g. 'Tokyo'."},
            "status": {"type": "string", "enum": ["planned", "booked", "completed"],
                       "description": "Trip status to filter on."},
        },
        "required": [],
    },
)
def list_trips(args, tool):
    rows = boundaries.read("student-1-db", "/trips", params=args)
    return boundaries.cap(rows, tool["rowLimit"])


@register(
    "get_trip_itinerary",
    "Return one trip with its day-by-day itinerary.",
    owner="student-1",
    target="student-1-db",
    input_schema={
        "properties": {
            "trip_id": {"type": "integer", "minimum": 1,
                        "description": "The trip to fetch."},
        },
        "required": ["trip_id"],
    },
    row_limit=30,
)
def get_trip_itinerary(args, tool):
    trip = boundaries.read("student-1-db", f"/trips/{args['trip_id']}")
    days = boundaries.read("student-1-db", "/days", params={"trip_id": args["trip_id"]})
    capped, truncated = boundaries.cap(days, tool["rowLimit"])
    return [{"trip": trip, "days": capped}], truncated


# --- Student 2 : Sightseeing, attractions & dining --------------------------

@register(
    "search_places",
    "Search attractions and restaurants by category or name.",
    owner="student-2",
    target="student-2-db",
    input_schema={
        "properties": {
            "category": {"type": "string", "maxLength": 40,
                         "description": "Partial category, e.g. 'restaurant'."},
            "name": {"type": "string", "maxLength": 60,
                     "description": "Partial place name."},
        },
        "required": [],
    },
)
def search_places(args, tool):
    # student-2-db /places takes no query parameters, so the filter is applied
    # here rather than pushed down. Reading the whole (small, seeded) table and
    # narrowing it is honest about where the work happens.
    rows = boundaries.read("student-2-db", "/places")
    category = (args.get("category") or "").lower()
    name = (args.get("name") or "").lower()
    if category:
        rows = [r for r in rows if category in (r.get("category") or "").lower()]
    if name:
        rows = [r for r in rows if name in (r.get("name") or "").lower()]
    return boundaries.cap(rows, tool["rowLimit"])


# --- Student 3 : Travel mate matching ---------------------------------------

@register(
    "find_travel_mates",
    "Find open trip posts from travellers looking for a travel mate.",
    owner="student-3",
    target="student-3-db",
    input_schema={
        "properties": {
            "destination": {"type": "string", "maxLength": 60,
                            "description": "Partial destination name."},
            "status": {"type": "string", "enum": ["open", "matched", "closed"],
                       "description": "Post status to filter on."},
        },
        "required": [],
    },
)
def find_travel_mates(args, tool):
    rows = boundaries.read("student-3-db", "/trip_posts", params=args)
    return boundaries.cap(rows, tool["rowLimit"])


# --- Student 4 : Accounts, profile & travel guides --------------------------

@register(
    "lookup_destination_guide",
    "Look up travel-guide destinations by city or country.",
    owner="student-4",
    target="student-4-db",
    input_schema={
        "properties": {
            "query": {"type": "string", "maxLength": 60,
                      "description": "Partial city or country name."},
        },
        "required": ["query"],
    },
)
def lookup_destination_guide(args, tool):
    rows = boundaries.read("student-4-db", "/destinations", params=args)
    return boundaries.cap(rows, tool["rowLimit"])


# --- Student 5 : Flights, hotels & budget -----------------------------------

@register(
    "search_flights",
    "Search available flights by origin, destination and budget ceiling.",
    owner="student-5",
    target="student-5-db",
    input_schema={
        "properties": {
            "origin": {"type": "string", "maxLength": 60,
                       "description": "Partial origin city."},
            "destination": {"type": "string", "maxLength": 60,
                            "description": "Partial destination city."},
            "budget_aud": {"type": "integer", "minimum": 1, "maximum": 100000,
                           "description": "Maximum fare in AUD."},
        },
        "required": [],
    },
)
def search_flights(args, tool):
    rows = boundaries.read("student-5-db", "/flights/search", params=args)
    return boundaries.cap(rows, tool["rowLimit"])
