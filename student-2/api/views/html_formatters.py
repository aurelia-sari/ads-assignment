"""
HTML formatters for frontend. (student-2, Kevin Kim)

Converts database JSON responses into HTML fragments
returned to HTMX.
"""


# Places HTML formatter
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
        image_url = (
            place["image_url"]
            or "/shared/assets/place-placeholder.png"
        )

        # Format price
        price = place["price_range"]

        if price == 0:
            price_display = "Free"
        elif price is None:
            price_display = "-"
        else:
            price_display = f"A${price}"

        html.append(
            f"""
            <div class="card" style="margin-bottom:1rem">
                <div style="
                    display:grid;
                    grid-template-columns:minmax(0, 1fr) 260px;
                    gap:2rem;
                    align-items:stretch;
                ">

                    <!-- Left side -->
                    <div>
                        <h3 style="margin-top:0">
                            {place["name"]}
                        </h3>

                        <p>
                            <strong>Category:</strong>
                            {place["category"].title()}
                        </p>

                        <p>
                            <strong>Address:</strong>
                            {place["address"]}
                        </p>

                        <p>
                            <strong>Rating:</strong>
                            {place["rating"] or "-"}
                        </p>

                        <p>
                            <strong>Average Price:</strong>
                            {price_display}
                        </p>

                        <p>
                            <strong>Opening Hours:</strong>
                            {place["opening_hours"] or "-"}
                        </p>

                        <p>
                            <strong>Description:</strong>
                            {place["description"] or ""}
                        </p>
                    </div>

                    <!-- Right side -->
                    <div style="
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        gap:1rem;
                        min-height:230px;
                    ">

                        <img
                            src="{image_url}"
                            alt="{place["name"]}"
                            style="
                                width:100%;
                                height:160px;
                                object-fit:cover;
                                border-radius:8px;
                                display:block;
                            "
                        >

                        <div style="
                            display:flex;
                            justify-content:flex-end;
                            gap:0.75rem;
                            flex-wrap:wrap;
                        ">

                            <button
                                type="button"
                                hx-post="/api/student-2/favourites"
                                hx-vals='{{"place_id":"{place["id"]}"}}'
                                hx-target="#favourites-panel"
                                hx-swap="innerHTML">
                                Add Favourite
                            </button>

                            <button
                                type="button"
                                class="btn-danger"
                                hx-delete="/api/student-2/places/{place["id"]}"
                                hx-target="#places-panel"
                                hx-swap="innerHTML">
                                Delete Place
                            </button>

                        </div>

                    </div>

                </div>
            </div>
            """
        )

    return "".join(html)


# Favourites HTML formatter
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
        image_url = (
            favourite["image_url"]
            or "/shared/assets/place-placeholder.png"
        )

        # Format price
        price = favourite["price_range"]

        if price == 0:
            price_display = "Free"
        elif price is None:
            price_display = "-"
        else:
            price_display = f"A${price}"

        html.append(
            f"""
            <div class="card" style="margin-bottom:1rem">
                <div style="
                    display:grid;
                    grid-template-columns:minmax(0, 1fr) 260px;
                    gap:2rem;
                    align-items:stretch;
                ">

                    <!-- Left side -->
                    <div>

                        <h3 style="margin-top:0">
                            {favourite["place_name"]}
                        </h3>

                        <p>
                            <strong>User:</strong>
                            {favourite["user_id"]}
                        </p>

                        <p>
                            <strong>Category:</strong>
                            {favourite["category"].title()}
                        </p>

                        <p>
                            <strong>Address:</strong>
                            {favourite["address"]}
                        </p>

                        <p>
                            <strong>Rating:</strong>
                            {favourite["rating"] or "-"}
                        </p>

                        <p>
                            <strong>Average Price:</strong>
                            {price_display}
                        </p>

                        <p>
                            <strong>Notes:</strong>
                            {favourite["notes"] or "-"}
                        </p>

                        <p class="muted">
                            Saved on {favourite["created_at"]}
                        </p>

                    </div>

                    <!-- Right side -->
                    <div style="
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        gap:1rem;
                        min-height:230px;
                    ">

                        <img
                            src="{image_url}"
                            alt="{favourite["place_name"]}"
                            style="
                                width:100%;
                                height:160px;
                                object-fit:cover;
                                border-radius:8px;
                                display:block;
                            "
                        >

                        <div style="
                            display:flex;
                            justify-content:flex-end;
                        ">

                            <button
                                type="button"
                                class="btn-danger"
                                hx-delete="/api/student-2/favourites/{favourite["id"]}"
                                hx-target="#favourites-panel"
                                hx-swap="innerHTML">
                                Delete Favourite
                            </button>

                        </div>

                    </div>

                </div>
            </div>
            """
        )

    return "".join(html)