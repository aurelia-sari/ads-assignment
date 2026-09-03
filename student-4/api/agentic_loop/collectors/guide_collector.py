"""Act step: retrieve the guide facts a question needs (student-4, Aurelia Sari)."""

from services import database_api


def collect_destinations():
    response = database_api.get_destinations()
    if response.status_code != 200:
        return []
    return response.json()


def collect_destination(destination_id):
    response = database_api.get_destination(destination_id)
    if response.status_code != 200:
        return None
    return response.json()


def collect_currency(destination_id):
    response = database_api.get_currency(destination_id)
    if response.status_code != 200:
        return None
    return response.json()


def collect_transportation(destination_id):
    response = database_api.get_transportation(destination_id)
    if response.status_code != 200:
        return []
    return response.json()


def collect_visa(destination_id):
    response = database_api.get_visa(destination_id)
    if response.status_code != 200:
        return []
    return response.json()


def collect_weather(destination_id):
    response = database_api.get_weather(destination_id)
    if response.status_code != 200:
        return []
    return response.json()


def collect_safety(destination_id):
    response = database_api.get_safety(destination_id)
    if response.status_code != 200:
        return None
    return response.json()


def collect_redirect_map():
    return database_api.get_feature_redirect_map()
