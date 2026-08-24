"""HTML fragment builders returned to HTMX.

Everything user-supplied goes through escape() before it reaches the page.
"""

from html import escape

STATUS_PILLS = {
    "planned": "pill-planned",
    "booked": "pill-booked",
    "completed": "pill-completed",
    "cancelled": "pill-cancelled",
}


def notice(message, kind="ok"):
    return f"<div class='notice notice-{kind}'>{escape(message)}</div>"


def error_fragment(message, detail=""):
    body = notice(message, "error")
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body


def status_pill(status):
    css = STATUS_PILLS.get(status, "pill-planned")
    return f"<span class='pill {css}'>{escape(status)}</span>"


def trips_table(trips):
    if not trips:
        return "<p class='muted'>No trips match this search.</p>"

    rows = []
    for trip in trips:
        trip_id = trip["trip_id"]
        rows.append(
            "<tr>"
            f"<td>{trip_id}</td>"
            f"<td>{escape(trip['trip_name'])}</td>"
            f"<td>{escape(trip['destination'])}</td>"
            f"<td>{escape(trip['start_date'])}</td>"
            f"<td>{escape(trip['end_date'])}</td>"
            f"<td>${trip['budget_aud']:,.0f}</td>"
            f"<td>{status_pill(trip['status'])}</td>"
            "<td>"
            f"<button class='btn-sm' hx-get='/api/student-1/trips/{trip_id}/days' "
            f"hx-target='#itinerary-panel' hx-swap='innerHTML'>Days</button> "
            f"<button class='btn-sm btn-secondary' hx-get='/api/student-1/trips/{trip_id}/edit' "
            f"hx-target='#trip-form-panel' hx-swap='innerHTML'>Edit</button> "
            f"<button class='btn-sm btn-danger' hx-delete='/api/student-1/trips/{trip_id}' "
            f"hx-target='#trips-panel' hx-swap='innerHTML' "
            f"hx-confirm='Delete trip {escape(trip['trip_name'])} and its itinerary days?'>Delete</button>"
            "</td>"
            "</tr>"
        )

    return (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>ID</th><th>Trip</th><th>Destination</th><th>Start</th>"
        "<th>End</th><th>Budget</th><th>Status</th><th>Actions</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        f"<p class='muted'>{len(trips)} trip(s).</p>"
    )


def trip_form(trip=None):
    """Create form when trip is None, otherwise an update form."""
    is_edit = trip is not None
    trip = trip or {}
    trip_id = trip.get("trip_id")

    attrs = (
        f"hx-put='/api/student-1/trips/{trip_id}'"
        if is_edit
        else "hx-post='/api/student-1/trips'"
    )

    def value(field, default=""):
        return escape(str(trip.get(field, default)))

    options = "".join(
        f"<option value='{key}'{' selected' if trip.get('status') == key else ''}>{key}</option>"
        for key in STATUS_PILLS
    )

    return f"""
<form {attrs} hx-target='#trips-panel' hx-swap='innerHTML'>
  <h3 style='margin-top:0'>{'Update trip ' + str(trip_id) if is_edit else 'Add a trip'}</h3>
  <div class='form-grid'>
    <div><label>Trip name</label><input name='trip_name' value='{value("trip_name")}' required></div>
    <div><label>Destination</label><input name='destination' value='{value("destination")}' required></div>
    <div><label>Start date</label><input type='date' name='start_date' value='{value("start_date")}' required></div>
    <div><label>End date</label><input type='date' name='end_date' value='{value("end_date")}' required></div>
    <div><label>Traveller ID</label><input type='number' name='traveller_id' value='{value("traveller_id", 1)}' required></div>
    <div><label>Budget (AUD)</label><input type='number' step='0.01' name='budget_aud' value='{value("budget_aud", 0)}' required></div>
    <div><label>Status</label><select name='status'>{options}</select></div>
  </div>
  <button type='submit'>{'Save changes' if is_edit else 'Create trip'}</button>
  {"<button type='button' class='btn-secondary' hx-get='/api/student-1/trips/new' hx-target='#trip-form-panel' hx-swap='innerHTML'>Cancel</button>" if is_edit else ""}
  <span class='spinner'>saving...</span>
</form>
"""


def days_table(days, trip=None):
    heading = (
        f"<h3 style='margin-top:0'>Itinerary - {escape(trip['trip_name'])}</h3>"
        if trip
        else "<h3 style='margin-top:0'>Itinerary</h3>"
    )

    if not days:
        return heading + "<p class='muted'>No itinerary days yet for this trip.</p>" + (
            day_form(trip["trip_id"]) if trip else ""
        )

    rows = []
    for day in days:
        day_id = day["day_id"]
        rows.append(
            "<tr>"
            f"<td>{day['day_number']}</td>"
            f"<td>{escape(day['day_date'])}</td>"
            f"<td>{escape(day['location'])}</td>"
            f"<td style='white-space:normal'>{escape(day['activity'])}</td>"
            f"<td class='muted' style='white-space:normal'>{escape(day.get('notes') or '')}</td>"
            "<td>"
            f"<button class='btn-sm btn-danger' hx-delete='/api/student-1/days/{day_id}' "
            f"hx-target='#itinerary-panel' hx-swap='innerHTML'>Delete</button>"
            "</td>"
            "</tr>"
        )

    table = (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>Day</th><th>Date</th><th>Location</th><th>Activity</th>"
        "<th>Notes</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )
    return heading + table + (day_form(trip["trip_id"]) if trip else "")


def day_form(trip_id):
    return f"""
<form hx-post='/api/student-1/days' hx-target='#itinerary-panel' hx-swap='innerHTML'
      style='margin-top:1rem'>
  <input type='hidden' name='trip_id' value='{trip_id}'>
  <div class='form-grid'>
    <div><label>Day number</label><input type='number' name='day_number' min='1' required></div>
    <div><label>Date</label><input type='date' name='day_date' required></div>
    <div><label>Location</label><input name='location' required></div>
    <div><label>Activity</label><input name='activity' required></div>
    <div><label>Notes</label><input name='notes'></div>
  </div>
  <button type='submit'>Add day</button>
  <span class='spinner'>saving...</span>
</form>
"""


def chat_exchange(question, answer):
    return (
        "<div class='chat-msg user'><div class='who'>You</div>"
        f"<div class='bubble'>{escape(question)}</div></div>"
        "<div class='chat-msg bot'><div class='who'>Wander AI</div>"
        f"<div class='bubble'>{escape(answer)}</div></div>"
    )
