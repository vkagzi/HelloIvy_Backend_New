from datetime import datetime, timedelta
import os
import jwt

JWT_SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "",
)
ALGORITHM = "HS256"


def generate_jwt_token(email: str, token: str) -> str:
    payload = {
        "email": email,
        "token": token,
        "exp": datetime.now() + timedelta(days=365),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)
