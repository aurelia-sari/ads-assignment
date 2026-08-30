"""
HTML formatters for frontend. (student-2, Kevin Kim)

Converts database JSON responses into HTML fragments
returned to HTMX.
"""

from html import escape


CATEGORY_OPTIONS = (
    "attraction",
    "restaurant",
    "activities",
)

PRICE_RANGE_OPTIONS = (
    0,
    10,
    30,
    50,
    70,
    100,
    200,
)


# =========================================================
# Shared icons
# =========================================================

HEART_ICON = """
<svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    style="width:17px;height:17px;flex-shrink:0;"
>
    <path
        d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1
           a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6
           1-1a5.5 5.5 0 0 0 0-7.8z">
    </path>
</svg>
"""


TRASH_ICON = """
<svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    style="width:17px;height:17px;flex-shrink:0;"
>
    <polyline points="3 6 5 6 21 6"></polyline>
    <path d="M19 6l-1 14H6L5 6"></path>
    <path d="M8 6V4h8v2"></path>
    <line x1="10" y1="10" x2="10" y2="17"></line>
    <line x1="14" y1="10" x2="14" y2="17"></line>
</svg>
"""


# =========================================================
# Error fragment
# =========================================================

def error_fragment(message, detail=""):
    """Render an error notice."""

    body = (
        f"<div class='notice notice-error'>"
        f"{escape(message)}"
        f"</div>"
    )

    if detail:
        body += (
            f"<pre>"
            f"{escape(str(detail)[:600])}"
            f"</pre>"
        )

    return body


# =========================================================
# Edit place form
# =========================================================

def format_place_edit_form(place):
    """Render a pre-filled form that updates a single place."""

    def value(field, default=""):
        raw_value = (
            place.get(field)
            if place.get(field) is not None
            else default
        )

        return escape(str(raw_value))

    category_options = "".join(
        f"<option value='{option}'"
        f"{' selected' if place.get('category') == option else ''}>"
        f"{option.title()}</option>"
        for option in CATEGORY_OPTIONS
    )

    price_options = "".join(
        f"<option value='{option}'"
        f"{' selected' if place.get('price_range') == option else ''}>"
        f"{option}</option>"
        for option in PRICE_RANGE_OPTIONS
    )

    return f"""
    <form
        hx-put="/api/student-2/places/{place['id']}"
        hx-target="#places-list"
        hx-swap="innerHTML"
        hx-on::after-request="
            if(event.detail.successful){{
                alert('Place updated successfully.');
                location.reload();
            }}
        "
    >

        <h4 style="margin-bottom:1.25rem;">
            Update Place #{place['id']}
        </h4>

        <div class="form-grid">

            <div>
                <label>Name</label>
                <input
                    name="name"
                    value="{value('name')}"
                    required
                >
            </div>

            <div>
                <label>Category</label>
                <select name="category">
                    {category_options}
                </select>
            </div>

            <div>
                <label>Address</label>
                <input
                    name="address"
                    value="{value('address')}"
                    required
                >
            </div>

            <div>
                <label>Rating</label>
                <input
                    type="number"
                    min="0.0"
                    max="5.0"
                    step="0.1"
                    name="rating"
                    value="{value('rating')}"
                >
            </div>

            <div>
                <label>Price Range</label>
                <select name="price_range">
                    {price_options}
                </select>
            </div>

            <div>
                <label>Image URL</label>
                <input
                    type="url"
                    name="image_url"
                    value="{value('image_url')}"
                    placeholder="https://example.com/photo.jpg"
                >
            </div>

            <div style="grid-column:1/-1;">
                <label>Description</label>
                <textarea name="description">{value('description')}</textarea>
            </div>

        </div>

        <button type="submit">
            Save changes
        </button>

        <span class="spinner">
            saving...
        </span>

    </form>
    """


# =========================================================
# Places HTML formatter
# =========================================================

def format_places(places):
    """Convert place records into an HTML fragment."""

    if not places:
        return """
        <div class="notice">
            No places available.
        </div>
        """

    html = []

    for place in places:

        name = escape(str(place.get("name", "")))
        category = escape(
            str(place.get("category", "")).title()
        )
        address = escape(str(place.get("address", "")))
        rating = escape(
            str(place.get("rating") or "-")
        )
        opening_hours = escape(
            str(place.get("opening_hours") or "-")
        )
        description = escape(
            str(place.get("description") or "")
        )

        image_url = escape(
            str(
                place.get("image_url")
                or "/shared/assets/place-placeholder.png"
            )
        )

        price = place.get("price_range")

        if price == 0:
            price_display = "Free"
        elif price is None:
            price_display = "-"
        else:
            price_display = f"A${price}"

        html.append(
            f"""
            <div
                class="card"
                style="margin-bottom:1.25rem;"
            >

                <div style="
                    display:grid;
                    grid-template-columns:minmax(0,1fr) 260px;
                    gap:2rem;
                    align-items:stretch;
                ">

                    <!-- Left -->
                    <div>

                        <h3 style="
                            margin:0 0 1.25rem 0;
                            font-family:var(--font-display);
                            font-size:1.4rem;
                            font-weight:700;
                            line-height:1.3;
                        ">
                            {name}
                        </h3>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Category:</strong>
                            {category}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Address:</strong>
                            {address}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Rating:</strong>
                            {rating}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Average Price:</strong>
                            {price_display}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Opening Hours:</strong>
                            {opening_hours}
                        </p>

                        <p style="margin-bottom:0;line-height:1.6;">
                            <strong>Description:</strong>
                            {description}
                        </p>

                    </div>


                    <!-- Right -->
                    <div style="
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        gap:1rem;
                        min-height:230px;
                    ">

                        <img
                            src="{image_url}"
                            alt="{name}"
                            style="
                                width:100%;
                                height:160px;
                                object-fit:cover;
                                border-radius:10px;
                                display:block;
                            "
                        >


                        <div style="
                            display:flex;
                            justify-content:flex-end;
                            gap:0.75rem;
                            flex-wrap:wrap;
                        ">

                            <!-- Add Favourite -->
                            <button
                                type="button"
                                class="place-action-btn place-action-btn--favourite"
                                hx-post="/api/student-2/favourites"
                                hx-vals='{{"place_id":"{place["id"]}"}}'
                                hx-target="#favourites-list"
                                hx-swap="innerHTML"
                                hx-on::after-request="
                                    if(event.detail.successful){{
                                        alert('Added to favourites.');
                                        location.reload();
                                    }}
                                "
                                style="
                                    display:inline-flex;
                                    align-items:center;
                                    justify-content:center;
                                    gap:0.5rem;
                                "
                            >
                                {HEART_ICON}
                                <span>Add Favourite</span>
                            </button>


                            <!-- Delete Place -->
                            <button
                                type="button"
                                class="place-action-btn place-action-btn--delete"
                                hx-delete="/api/student-2/places/{place["id"]}"
                                hx-target="#places-list"
                                hx-swap="innerHTML"
                                hx-confirm="Delete {name}?"
                                hx-on::after-request="
                                    if(event.detail.successful){{
                                        alert('Place deleted successfully.');
                                        location.reload();
                                    }}
                                "
                                style="
                                    background:#b3261e;
                                    display:inline-flex;
                                    align-items:center;
                                    justify-content:center;
                                    gap:0.5rem;
                                "
                            >
                                {TRASH_ICON}
                                <span>Delete Place</span>
                            </button>

                        </div>

                    </div>

                </div>

            </div>
            """
        )

    return "".join(html)


# =========================================================
# Favourites HTML formatter
# =========================================================

def format_favourites(favourites):
    """Convert favourite records into an HTML fragment."""

    if not favourites:
        return """
        <div class="notice">
            No favourites found.
        </div>
        """

    html = []

    for favourite in favourites:

        place_name = escape(
            str(favourite.get("place_name", ""))
        )

        user_id = escape(
            str(favourite.get("user_id", ""))
        )

        category = escape(
            str(favourite.get("category", "")).title()
        )

        address = escape(
            str(favourite.get("address", ""))
        )

        rating = escape(
            str(favourite.get("rating") or "-")
        )

        notes = escape(
            str(favourite.get("notes") or "-")
        )

        created_at = escape(
            str(favourite.get("created_at", ""))
        )

        image_url = escape(
            str(
                favourite.get("image_url")
                or "/shared/assets/place-placeholder.png"
            )
        )

        price = favourite.get("price_range")

        if price == 0:
            price_display = "Free"
        elif price is None:
            price_display = "-"
        else:
            price_display = f"A${price}"

        html.append(
            f"""
            <div
                class="card"
                style="margin-bottom:1.25rem;"
            >

                <div style="
                    display:grid;
                    grid-template-columns:minmax(0,1fr) 260px;
                    gap:2rem;
                    align-items:stretch;
                ">

                    <!-- Left -->
                    <div>

                        <h3 style="
                            margin:0 0 1.25rem 0;
                            font-family:var(--font-display);
                            font-size:1.4rem;
                            font-weight:700;
                            line-height:1.3;
                        ">
                            {place_name}
                        </h3>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>User:</strong>
                            {user_id}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Category:</strong>
                            {category}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Address:</strong>
                            {address}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Rating:</strong>
                            {rating}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Average Price:</strong>
                            {price_display}
                        </p>

                        <p style="margin-bottom:0.55rem;line-height:1.6;">
                            <strong>Notes:</strong>
                            {notes}
                        </p>

                        <p
                            class="muted"
                            style="
                                margin-top:0.9rem;
                                margin-bottom:0;
                                line-height:1.6;
                            "
                        >
                            Saved on {created_at}
                        </p>

                    </div>


                    <!-- Right -->
                    <div style="
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        gap:1rem;
                        min-height:230px;
                    ">

                        <img
                            src="{image_url}"
                            alt="{place_name}"
                            style="
                                width:100%;
                                height:160px;
                                object-fit:cover;
                                border-radius:10px;
                                display:block;
                            "
                        >


                        <div style="
                            display:flex;
                            justify-content:flex-end;
                        ">

                            <button
                                type="button"
                                class="place-action-btn place-action-btn--delete"
                                hx-delete="/api/student-2/favourites/{favourite["id"]}"
                                hx-target="#favourites-list"
                                hx-swap="innerHTML"
                                hx-confirm="Remove {place_name} from favourites?"
                                hx-on::after-request="
                                    if(event.detail.successful){{
                                        alert('Removed from favourites.');
                                        location.reload();
                                    }}
                                "
                                style="
                                    background:#b3261e;
                                    display:inline-flex;
                                    align-items:center;
                                    justify-content:center;
                                    gap:0.5rem;
                                "
                            >
                                {TRASH_ICON}
                                <span>Delete Favourite</span>
                            </button>

                        </div>

                    </div>

                </div>

            </div>
            """
        )

    return "".join(html)