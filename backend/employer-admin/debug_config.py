from app.config import Settings
from pydantic import ValidationError

try:
    settings = Settings()
    print("Settings loaded successfully")
except ValidationError as e:
    print(e)
except Exception as e:
    print(f"An error occurred: {e}")
