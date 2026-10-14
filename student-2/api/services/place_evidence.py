"""City-scoped search_places evidence and deterministic table validation.

Uses the existing supplied-evidence API. Shared services remain unchanged.
"""
import json
import re
import requests
from services import mcp_client
from services.multi_agent_client import MultiAgentError

# Inclusive metro bounds cover suburb addresses which omit the city name.
CITIES = {
    "Sydney": ((-34.15, -33.55, 150.75, 151.40), ("sydney", "시드니")),
    "Melbourne": ((-38.10, -37.50, 144.50, 145.50), ("melbourne", "멜버른")),
    "Brisbane": ((-27.75, -27.15, 152.65, 153.40), ("brisbane", "브리즈번")),
    "Tokyo": ((35.45, 35.90, 139.45, 139.95), ("tokyo", "도쿄")),
    "Osaka": ((34.45, 34.90, 135.20, 135.75), ("osaka", "오사카")),
    "Sapporo": ((42.90, 43.30, 141.05, 141.65), ("sapporo", "삿포로")),
}
SCHEMA = "student2-city-places-v1"
MAX_PER_CATEGORY = 4
TIME = r"(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:[ap]\.?m\.?)?"
RANGE = re.compile(rf"({TIME})\s*(?:-|–|—|to|until)\s*({TIME})", re.I)
TIME_CLAIM = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b|\b\d{1,2}\s*(?:am|pm)\b|24\s*/\s*7", re.I)


def task_city(task, selected):
    found = [city for city, (_, aliases) in CITIES.items() if any(
        re.search(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", task, re.I) for alias in aliases)]
    if not selected and len(found) == 1:
        selected = found[0]
    if selected not in CITIES:
        raise MultiAgentError("Mention one supported city in your request or choose City in the optional filters.", 400)
    if any(city != selected for city in found):
        raise MultiAgentError("The request mentions a different city. Use one city matching the selected city.", 400)
    return selected


def in_city(row, city):
    bounds, aliases = CITIES[city]
    address = str(row.get("address") or "").lower()
    # An explicit different city overrides inconsistent coordinates.
    for other, (_, names) in CITIES.items():
        if other != city and any(re.search(r"\b" + re.escape(name) + r"\b", address) for name in names):
            return False
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        return bounds[0] <= lat <= bounds[1] and bounds[2] <= lon <= bounds[3]
    except (KeyError, TypeError, ValueError):
        return any(re.search(r"\b" + re.escape(alias) + r"\b", address) for alias in aliases)


def task_category(task, selected):
    if selected:
        return selected
    kinds = []
    for category, pattern in (("attraction", r"attraction|sightseeing|관광|명소"), ("restaurant", r"dining|restaurant|food|meal|식사|음식|맛집"), ("activity", r"activit|experience|활동|체험")):
        if re.search(pattern, task, re.I):
            kinds.append(category)
    return kinds[0] if len(kinds) == 1 else "all"


def required_categories(task, selected):
    attractions = re.search(r"attraction|sightseeing|관광|명소", task, re.I)
    dining = re.search(r"dining|restaurant|food|meal|식사|음식|맛집", task, re.I)
    if selected == "all" or (attractions and dining):
        return ["attraction", "restaurant"]
    return [selected]


def recommendation(row, city):
    role = {"attraction": "Sightseeing", "restaurant": "Dining", "activity": "Activity"}[row["category"]]
    description = str(row.get("description") or "").replace("|", "/").replace("\n", " ").strip()[:140]
    rating = row.get("rating")
    reason = f"{role} stop in {city}"
    if description:
        reason += f": {description}"
    if rating is not None:
        reason += f" (recorded rating {rating}/5)"
    return reason


def bundle(supplied, required):
    bodies = [json.loads(item["content"]) for item in supplied]
    groups = {category: [row for body in bodies for row in body["places"] if row["category"] == category] for category in required}
    missing = [category for category, rows in groups.items() if not rows]
    if missing:
        raise MultiAgentError("Cannot fulfil the requested categories with this city/name filter: " + ", ".join(missing) + ". Clear the name filter or change city.", 422)
    for body in bodies:
        body["required_categories"] = required
    if set(required) == {"attraction", "restaurant"}:
        pairs = []
        for i in range(max(len(groups[c]) for c in required)):
            base = dict(bodies[0])
            base["places"] = [groups[c][i % len(groups[c])] for c in required]
            base["arguments"] = [{"category": c, **({"name": bodies[0]["arguments"]["name"]} if bodies[0]["arguments"].get("name") else {})} for c in required]
            base["matched_count"] = {c: next(b["matched_count"] for b in bodies if b["arguments"]["category"] == c) for c in required}
            base["offered_count"] = {c: len(groups[c]) for c in required}
            pairs.append(base)
        bodies = pairs + [b for b in bodies if b["arguments"]["category"] not in required]
    result = []
    for body in bodies:
        content = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        if len(content) > 2000:
            raise MultiAgentError("A combined evidence record is too large. Narrow the request.", 422)
        names = " + ".join(row["name"] for row in body["places"]) or "No matching places"
        result.append({"label": f"{body['city']}: {names} (search_places)", "content": content})
    return result


def collect(city, categories, name, required=None):
    supplied = []
    for category in categories:
        try:
            result = mcp_client.search_places(category, name or None)
        except requests.Timeout as exc:
            raise MultiAgentError("Place evidence search timed out; no workflow was started.", 504) from exc
        except (requests.RequestException, mcp_client.MCPDisabled) as exc:
            raise MultiAgentError("Place evidence is unavailable; no workflow was started.", 503) from exc
        except mcp_client.MCPProtocolError as exc:
            raise MultiAgentError(str(exc), 502) from exc
        rows = result["structuredContent"].get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise MultiAgentError("search_places returned invalid place rows.", 502)
        matches = [row for row in rows if row.get("category") == category and in_city(row, city)
                   and isinstance(row.get("name"), str) and row["name"].strip()]
        def rating(row):
            try: return float(row.get("rating") or 0)
            except (ValueError, TypeError): return 0
        matches.sort(key=lambda row: (-rating(row), row["name"]))
        selected = matches[:MAX_PER_CATEGORY]
        # One compact record per source avoids shared-server character clipping.
        records = selected or [None]
        for row in records:
            places = [] if row is None else [{
                "name": row["name"], "category": category, "city": city,
                "address": str(row.get("address") or ""),
                "latitude": row.get("latitude"), "longitude": row.get("longitude"),
                "opening_hours": str(row.get("opening_hours") or "Unknown — check official schedule"),
                "rating": row.get("rating"),
                "recommendation_reason": recommendation(row, city),
            }]
            envelope = {"schema": SCHEMA, "city": city, "tool": "search_places",
                        "arguments": {"category": category, **({"name": name} if name else {})},
                        "matched_count": len(matches), "offered_count": len(selected), "places": places,
                        "note": "Recorded hours are database values, not live availability. No match means do not invent a place."}
            content = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
            if len(content) > 2000:
                raise MultiAgentError("A place record exceeds the safe evidence size; narrow the place search.", 422)
            supplied.append({"label": f"{city} {category}: {row['name'] if row else 'no matching places'} (search_places)", "content": content})
    if not any(json.loads(item["content"])["places"] for item in supplied):
        raise MultiAgentError(f"No matching places in {city}. Try another category or name filter.", 422)
    return bundle(supplied, required) if required else supplied


def instruction(task, city, required=None):
    needs = ", ".join(required or [])
    return (f"City: {city}. {task}\n"
            f"Required categories: {needs}. Planner: select evidence covering these categories. "
            "Worker: output ONLY a FIVE-column Markdown table. Keep Reason and Evidence separate. "
            "Use one row per supplied place; do not expect extra places. Include every required category:\n"
            "| Place | City | Opening hours | Reason | Evidence |\n| --- | --- | --- | --- | --- |\n"
            "Map JSON fields exactly: name -> Place; city -> City; opening_hours -> Opening hours; "
            "recommendation_reason -> Reason. Reason MUST copy the full recommendation_reason text, never Available. "
            "Evidence is the enclosing [E#]. Unknown hours stay Unknown. Recorded hours are not live availability. "
            "No text outside the table.")


def evidence_rows(workflow):
    rows, cities, problems = {}, set(), []
    for item in workflow.get("evidence", []):
        if not item.get("ok"):
            problems.append("An evidence source was unavailable."); continue
        try:
            body = json.loads(item.get("content", ""))
        except (TypeError, ValueError):
            problems.append("Legacy or truncated evidence cannot be verified; run a new city-scoped workflow."); continue
        if not isinstance(body, dict) or body.get("schema") != SCHEMA or body.get("city") not in CITIES:
            problems.append("Evidence has no student-2 city scope; run a new workflow."); continue
        city = body["city"]; cities.add(city)
        for row in body.get("places", []):
            if not isinstance(row, dict) or row.get("city") != city or not in_city(row, city):
                problems.append("An evidence row does not match its city scope."); continue
            rows.setdefault(row["name"].casefold(), []).append((item["id"], row))
    return rows, cities, problems


def clock(value):
    clean = re.sub(r"[.\s]", "", value.lower())
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", clean)
    if not m: return None
    hour, minute = int(m[1]), int(m[2] or 0)
    if minute > 59 or (m[3] and not 1 <= hour <= 12) or (not m[3] and hour > 23): return None
    if m[3]: hour = hour % 12 + (12 if m[3] == "pm" else 0)
    return hour * 60 + minute


def hour_ranges(text):
    return [(clock(m[1]), clock(m[2])) for m in RANGE.finditer(text)]


def same_hours(claim, recorded):
    normal = lambda s: re.sub(r"[\s*_`.]", "", s.casefold()).replace("–", "-").replace("—", "-")
    if normal(claim) == normal(recorded): return True
    expected, actual = hour_ranges(recorded), hour_ranges(claim)
    if expected:
        # Range only is acceptable; qualifiers (weekdays/seasonal) must be retained.
        qualifiers = RANGE.sub("", recorded).strip(" ;,.")
        return bool(actual) and actual == expected and not qualifiers
    return not actual and bool(re.fullmatch(r"(?:unknown|not available|not provided|check official schedule|see official schedule)", claim.strip(), re.I))


def table_rows(text):
    lines = text.splitlines(); found = []
    for i, line in enumerate(lines[:-1]):
        cells = [c.strip().strip("*` ") for c in line.strip().strip("|").split("|")]
        aliases = {"recommendation reason": "reason", "recorded opening hours": "opening hours", "source": "evidence"}
        headers = [aliases.get(c.casefold(), c.casefold()) for c in cells]
        if headers != ["place", "city", "opening hours", "reason", "evidence"]: continue
        separator = [c.strip() for c in lines[i+1].strip().strip("|").split("|")]
        if len(separator) != 5 or not all(re.fullmatch(r":?-{3,}:?", c) for c in separator): continue
        for row in lines[i+2:]:
            if "|" not in row: break
            values = [c.strip().strip("*` ") for c in row.strip().strip("|").split("|")]
            if len(values) == 5: found.append(values)
            else: found.append(["", "", "", "", ""])
    return found


def validate(workflow, response=None):
    rows, cities, issues = evidence_rows(workflow)
    latest = (workflow.get("attempts") or [{}])[-1]
    text = response if response is not None else latest.get("worker", {}).get("response", "")
    city = next(iter(cities)) if len(cities) == 1 else None
    if not city: issues.append("A single city scope could not be verified.")
    table = table_rows(text)
    if not table: issues.append("No verifiable place table. Run again or supply an edited Markdown table before accepting.")
    required = set()
    for item in workflow.get("sources", []):
        try:
            envelope = json.loads(item.get("content", ""))
            if isinstance(envelope, dict) and envelope.get("schema") == SCHEMA:
                required.update(envelope.get("required_categories", []))
        except (TypeError, ValueError):
            pass
    covered = set()
    checked = 0
    for name, claimed_city, hours, reason, refs in table:
        choices = rows.get(name.casefold(), [])
        if not choices:
            issues.append(f"{name or 'Unnamed place'}: not present in the city-scoped evidence."); continue
        checked += 1
        covered.update(row["category"] for _, row in choices)
        reasons = {row.get("recommendation_reason") for _, row in choices if row.get("recommendation_reason")}
        if reasons and reason not in reasons:
            issues.append(f"{name}: use the recorded recommendation reason, not Available or an unsupported claim.")
        elif not reasons and re.fullmatch(r"available|n/?a|none|unknown", reason.strip(), re.I):
            issues.append(f"{name}: a recommendation reason is required; availability has not been verified.")
        ids = {source for source, _ in choices}
        if claimed_city.casefold() != (city or "").casefold(): issues.append(f"{name}: city must be {city}.")
        if not any(same_hours(hours, row["opening_hours"]) for _, row in choices):
            issues.append(f"{name}: hours '{hours}' do not match recorded hours '{choices[0][1]['opening_hours']}'.")
        cited = set(re.findall(r"\[(E\d+)\]", refs))
        if not cited or not cited <= ids: issues.append(f"{name}: citation must reference its own place evidence ({', '.join(sorted(ids))}).")
        if RANGE.search(reason) or TIME_CLAIM.search(reason): issues.append(f"{name}: keep all time claims in the Opening hours column.")
    missing = required - covered
    if missing:
        issues.append("The result omits required categories: " + ", ".join(sorted(missing)) + ".")
    # Reject explicit mentions of other supported cities anywhere in the answer.
    for other, (_, aliases) in CITIES.items():
        if city and other != city and any(re.search(r"(?<![A-Za-z])"+re.escape(alias)+r"(?![A-Za-z])", text, re.I) for alias in aliases):
            issues.append(f"The response mentions {other}, outside the selected city {city}.")
    # No numeric hours should hide outside table rows.
    outside = "\n".join(line for line in text.splitlines() if "|" not in line)
    if RANGE.search(outside) or TIME_CLAIM.search(outside): issues.append("Time claims outside the table cannot be verified.")
    if required and any(line.strip() for line in outside.splitlines()):
        issues.append("Extra explanation outside the result table is not verified. Remove it before accepting.")
    issues = list(dict.fromkeys(issues))
    return {"city": city, "status": "concerns" if issues else "checked", "can_accept": not issues,
            "checked_places": checked, "issues": issues, "required_categories": sorted(required), "covered_categories": sorted(covered),
            "scope": "Checks required sightseeing/dining coverage, place names, city, recorded opening hours, evidence-based reasons and citations. It does not confirm live schedules or availability."}
