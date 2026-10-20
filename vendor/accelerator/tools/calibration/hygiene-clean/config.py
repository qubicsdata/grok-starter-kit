"""Configuration sourced from the environment — no hardcoded values."""
import os

PORT = int(os.environ.get("PORT", "8080"))
DB_PATH = os.environ.get("DB_PATH", "data.db")
