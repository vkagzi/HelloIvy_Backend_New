import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from utils.jwt import JWT_SECRET_KEY, ALGORITHM
from .models import User
from .dtos import UserDTO


class CustomJWTAuthentication(BaseAuthentication):

    def authenticate(self, request: Request) -> tuple[UserDTO | None, None]:

        # Extract the Bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None, None  # No authentication header provided

        token = auth_header.split(" ")[1]
        try:
            # Decode the JWT token
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            user = User.objects.get(
                email=payload["email"], token=payload["token"]
            ).to_dto()
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationFailed("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed("Invalid token") from e
        except User.DoesNotExist as e:
            raise AuthenticationFailed("User not found") from e

        return (user, None)  # Attach user to the request
