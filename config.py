import os
from dotenv import load_dotenv

load_dotenv()

NOMBA_ACCOUNT_ID = os.getenv("NOMBA_ACCOUNT_ID")
NOMBA_SUB_ACCOUNT_ID = os.getenv("NOMBA_SUB_ACCOUNT_ID")
NOMBA_CLIENT_ID = os.getenv("NOMBA_CLIENT_ID")
NOMBA_CLIENT_SECRET = os.getenv("NOMBA_CLIENT_SECRET")
NOMBA_BASE_URL = os.getenv("NOMBA_BASE_URL")

DATA_FILE = os.getenv("DATA_FILE", os.path.join(os.path.dirname(__file__), "data.json"))

CURRENCY = os.getenv("CURRENCY", "NGN")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
