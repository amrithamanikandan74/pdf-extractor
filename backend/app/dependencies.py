from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(x_api_key: str | None = Security(_api_key_scheme)) -> str:
    if x_api_key is None or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set the X-API-Key header.",
        )
    return x_api_key
