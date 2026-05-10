import jwt


def encode_jwt(payload: dict[str, object]) -> str:
    return jwt.encode(payload, key="", algorithm="none")
