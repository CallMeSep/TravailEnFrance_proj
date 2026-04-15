import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def get_access_token():
    # Read env at call-time so updated container/env values are honored.
    url = os.getenv("FT_TOKEN_URL")
    client_id = os.getenv("FT_CLIENT_ID")
    client_secret = os.getenv("FT_CLIENT_SECRET")
    scope = os.getenv("FT_SCOPE")

    missing = [
        name
        for name, value in (
            ("FT_TOKEN_URL", url),
            ("FT_CLIENT_ID", client_id),
            ("FT_CLIENT_SECRET", client_secret),
            ("FT_SCOPE", scope),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing France Travail env vars: "
            + ", ".join(missing)
            + ". Configure them before running ingestion."
        )

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    with httpx.Client() as client:
        response = client.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json().get("access_token")
