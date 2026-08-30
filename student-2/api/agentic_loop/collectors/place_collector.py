from services.database_api import get_places

# Collect places from database
def collect_places():
    places = get_places()

    return places

