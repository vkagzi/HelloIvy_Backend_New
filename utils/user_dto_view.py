from rest_framework.views import APIView

from apps.accounts.dtos import UserDTO


class UserDTOView(APIView):
    @property
    def user_dto(self) -> UserDTO:
        user = getattr(self.request, "user", None)
        if not isinstance(user, UserDTO):
            raise TypeError("Expected request.user to be an instance of UserDTO. Ensure the request is properly authenticated.")
        return user
