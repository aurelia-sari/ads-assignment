"""Database API client for the Travel Guides AI assistant (student-4, Aurelia Sari)."""

import os

import requests

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-4-db:5204")


def get_destinations():
    return requests.get(f"{DB_SERVICE_URL}/destinations", timeout=5)


def get_destination(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}", timeout=5)


def get_currency(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/currency", timeout=5)


def get_transportation(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/transportation", timeout=5)


def get_visa(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/visa", timeout=5)


def get_weather(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/weather", timeout=5)


def get_safety(destination_id):
    return requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/safety", timeout=5)


def get_feature_redirect_map():
    response = requests.get(f"{DB_SERVICE_URL}/feature-redirect-map", timeout=5)
    response.raise_for_status()
    return response.json()


def create_chat_session(user_id, destination_id):
    return requests.post(
        f"{DB_SERVICE_URL}/guide-chat-sessions",
        json={"user_id": user_id, "destination_id": destination_id},
        timeout=5,
    )


def get_chat_session(session_id):
    return requests.get(f"{DB_SERVICE_URL}/guide-chat-sessions/{session_id}", timeout=5)


def update_chat_session_destination(session_id, destination_id):
    return requests.patch(
        f"{DB_SERVICE_URL}/guide-chat-sessions/{session_id}",
        json={"destination_id": destination_id},
        timeout=5,
    )


def delete_chat_session(session_id):
    return requests.delete(f"{DB_SERVICE_URL}/guide-chat-sessions/{session_id}", timeout=5)


def add_chat_message(session_id, role, content, intent_category=None):
    return requests.post(
        f"{DB_SERVICE_URL}/guide-chat-sessions/{session_id}/messages",
        json={"role": role, "content": content, "intent_category": intent_category},
        timeout=5,
    )


def list_user_chat_sessions(user_id):
    return requests.get(f"{DB_SERVICE_URL}/users/{user_id}/guide-chat-sessions", timeout=5)
