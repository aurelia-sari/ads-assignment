from html import escape


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


def format_recommendation(question, result):
    answer = escape(
        str(result.get("answer", ""))
    ).replace("\n", "<br>")

    places = result.get("places", [])

    # =========================================================
    # Question + Answer
    # =========================================================

    html = f"""
    <div style="margin-bottom:2rem;">

        <div style="margin-bottom:1.8rem;">
            <strong>Question:</strong>

            <p style="
                margin-top:0.6rem;
                line-height:1.65;
            ">
                {escape(question)}
            </p>
        </div>


        <div>
            <strong>Answer:</strong>

            <p style="
                margin-top:0.6rem;
                line-height:1.65;
            ">
                {answer}
            </p>
        </div>

    </div>
    """

    # No valid recommended place found
    if not places:
        return html

    # =========================================================
    # Recommended places heading
    # =========================================================

    heading = (
        "Recommended Place"
        if len(places) == 1
        else "Recommended Places"
    )

    html += f"""
    <hr style="
        margin:2rem 0;
        border:0;
        border-top:1px solid var(--color-slate-200);
    ">

    <h3 style="margin-bottom:1.25rem;">
        {heading}
    </h3>
    """

    # =========================================================
    # Place cards
    # =========================================================

    for place in places:

        place_id = place.get("id")

        name = escape(
            str(place.get("name", ""))
        )

        category = escape(
            str(place.get("category", "")).title()
        )

        address = escape(
            str(place.get("address", ""))
        )

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

        html += f"""
        <div
            class="card"
            style="
                margin-bottom:1.25rem;
                display:grid;
                grid-template-columns:minmax(0,1fr) 300px;
                gap:2rem;
                align-items:stretch;
            "
        >

            <!-- Left -->
            <div>

                <h2 style="
                    margin:0 0 1.25rem 0;
                    font-family:var(--font-display);
                    font-size:1.45rem;
                    font-weight:700;
                    line-height:1.3;
                ">
                    {name}
                </h2>


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
            ">

                <img
                    src="{image_url}"
                    alt="{name}"
                    style="
                        width:100%;
                        height:190px;
                        object-fit:cover;
                        border-radius:12px;
                        display:block;
                    "
                >


                <button
                    type="button"
                    class="place-action-btn place-action-btn--favourite"
                    onclick="addFavourite({place_id})"
                    style="width:100%;"
                >
                    {HEART_ICON}
                    <span>Add Favourite</span>
                </button>

            </div>

        </div>
        """

    return html