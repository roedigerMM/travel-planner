from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
INSTANCE_DIR = BASE_DIR / "instance"

class Config:
    SECRET_KEY = "dev"
    INSTANCE_DIR.mkdir(exist_ok=True)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{(INSTANCE_DIR / 'app.sqlite').as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
    AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
    AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")