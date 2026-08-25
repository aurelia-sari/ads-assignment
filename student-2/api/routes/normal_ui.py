"""
Normal UI routes for Attractions & Dining. (student-2, Kevin Kim)

Handles HTMX requests for normal database-backed UI functions.
"""

from flask import Blueprint

from services.database_api import get_favourites, get_places
from views.html_formatters import format_favourites, format_places


normal_ui_bp = Blueprint("normal_ui", __name__)


# Places route
@normal_ui_bp.get("/places")
def places():
    places_data = get_places()
    return format_places(places_data)


# Favourites route
@normal_ui_bp.get("/favourites")
def favourites():
    favourites_data = get_favourites()
    return format_favourites(favourites_data)