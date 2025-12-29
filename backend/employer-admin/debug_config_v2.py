import os
from dotenv import load_dotenv
print(f"Current working directory: {os.getcwd()}")
print(f"Does .env exist? {os.path.exists('.env')}")
load_dotenv(verbose=True)
print("Environment variables after load_dotenv:")
print(f"MONGODB_URI: {os.getenv('MONGODB_URI')}")
print(f"FIREBASE_SERVICE_ACCOUNT_PATH: {os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')}")

from app.config import Settings
from pydantic import ValidationError

try:
    settings = Settings()
    print("Settings loaded successfully!")
    print(settings.model_dump())
except ValidationError as e:
    print("Validation Error:")
    print(e)
except Exception as e:
    print(f"An error occurred: {e}")
