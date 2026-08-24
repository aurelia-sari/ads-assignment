"""Trips & Itinerary backend/API (student-1).

Serves HTMX fragments to the student-1 frontend. Reads and writes trip data
only through student-1-db, and reaches the LLM only through the shared AI-Mode
service.
"""

from pathlib import Path
import sys

from flask import Flask
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from routes.ai_chat import ai_chat_bp
from routes.itinerary import itinerary_bp
from routes.trips import trips_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(trips_bp)
    app.register_blueprint(itinerary_bp)
    app.register_blueprint(ai_chat_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101)
