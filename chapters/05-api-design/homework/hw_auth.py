import hmac, hashlib, base64, json

def create_jwt(payload: dict, secret: str) -> str:
    # TODO: Create header, payload, and signature
    pass

def verify_jwt(token: str, secret: str) -> bool:
    pass
