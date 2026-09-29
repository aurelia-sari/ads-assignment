"""Database API client for the Travel Mate AI (student-3, Tanishpreet Kour)."""
 
import os
 
import requests
 
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://localhost:5203")
 
 
def get_trip_posts(**params):
    return requests.get(f"{DB_SERVICE_URL}/trip_posts", params=params, timeout=5)