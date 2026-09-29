"""MCP tests for Student 2."""

import os

import requests


MCP_URL = os.getenv("MCP_URL", "http://localhost:5400")
API_URL = os.getenv("STUDENT2_API_URL", "http://localhost:5102")
DB_URL = os.getenv("STUDENT2_DB_URL", "http://localhost:5202")


def expect(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  ok  {message}")


# Call shared MCP directly
def rpc(arguments):
    response = requests.post(
        f"{MCP_URL}/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "student-2-test",
            "method": "tools/call",
            "params": {"name": "search_places", "arguments": arguments},
        },
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()["result"]
    expect(not result["isError"], f"shared search_places accepts {arguments}")
    return result["structuredContent"]


# Call MCP through Student 2 API
def gateway(payload):
    return requests.post(f"{API_URL}/mcp/search-places", json=payload, timeout=15)


# Run MCP checks
def run_checks():
    health = requests.get(f"{MCP_URL}/health", timeout=5)
    expect(health.status_code == 200, "shared MCP health returns 200")

    restaurants = rpc({"category": "restaurant"})
    expect(restaurants["tool"] == "search_places", "shared MCP uses search_places")
    expect(restaurants["owner"] == "student-2", "tool boundary belongs to student-2")
    expect(bool(restaurants["rows"]), "restaurant search returns places")
    expect(
        all("restaurant" in row.get("category", "").lower() for row in restaurants["rows"]),
        "restaurant results match the category",
    )

    attractions = rpc({"category": "attraction"})
    expect(bool(attractions["rows"]), "attraction search returns places")
    expect(
        all("attraction" in row.get("category", "").lower() for row in attractions["rows"]),
        "attraction results match the category",
    )

    activities = rpc({"category": "activity"})
    expect(len(activities["rows"]) >= 5, "activity search returns the new city activities")
    expect(
        all(row.get("category") == "activity" for row in activities["rows"]),
        "activity results match the singular category",
    )

    tokyo_activity = rpc({"category": "activity", "name": "teamLab Planets Tokyo"})
    expect(tokyo_activity["row_count"] == 1, "new place name filter returns one match")

    sample_name = restaurants["rows"][0]["name"]
    named = rpc({"category": "restaurant", "name": sample_name})
    expect(named["row_count"] >= 1, "optional name filter returns a match")
    expect(any(row["name"] == sample_name for row in named["rows"]), "name result is exact")

    response = gateway({"category": "restaurant"})
    expect(response.status_code == 200, "Student 2 MCP endpoint returns 200")
    proxied = response.json()["structuredContent"]
    expect(proxied["rows"] == restaurants["rows"], "gateway preserves structured MCP rows")

    response = gateway({"category": "restaurant", "name": sample_name})
    expect(response.status_code == 200, "Student 2 gateway supports optional name")
    expect(response.json()["structuredContent"]["row_count"] >= 1, "gateway name filter works")

    expect(gateway({}).status_code == 400, "missing category returns 400")
    expect(gateway({"category": 7}).status_code == 400, "non-string category returns 400")
    expect(
        gateway({"category": "restaurant", "name": "x" * 61}).status_code == 400,
        "overlong name returns 400",
    )

    db_rows = requests.get(f"{DB_URL}/places", timeout=5).json()
    db_names = {row["name"] for row in db_rows if "restaurant" in row.get("category", "").lower()}
    expect({row["name"] for row in restaurants["rows"]} <= db_names, "MCP results match DB data")


if __name__ == "__main__":
    try:
        run_checks()
    except (AssertionError, KeyError, requests.RequestException) as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
    print("PASS: Student 2 MCP Release 1 checks completed.")
