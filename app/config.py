from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
INSTANCE_DIR = BASE_DIR / "instance"

class Config:
    SECRET_KEY = "dev"
    INSTANCE_DIR.mkdir(exist_ok=True)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{(INSTANCE_DIR / 'app.sqlite').as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
