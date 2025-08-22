from fastapi import HTTPException
from typing import Dict, Any


class APIException(HTTPException):
    def __init__(self, status_code: int, detail: str, headers: Dict[str, Any] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class SmartProxyException(APIException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=f"SmartProxy Error: {detail}")


class ValidationException(APIException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=f"Validation Error: {detail}")


class ConfigurationException(APIException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=f"Configuration Error: {detail}")


class RateLimitException(APIException):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail)


class ValidationError(APIException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=f"Validation Error: {detail}")