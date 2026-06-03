"""Configuration centralisée chargée depuis l'environnement (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI: str = os.getenv("MONGO_URI", "")
DB_NAME: str = os.getenv("DB_NAME", "dap_emiz")
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")

# Mot de passe commun aux comptes de démonstration (auth réelle, hash PBKDF2).
DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "demo1234")

ONCF_LOGO_URL: str = os.getenv(
    "ONCF_LOGO_URL",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/"
    "Logo-oncf.png/330px-Logo-oncf.png",
)
