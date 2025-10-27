# accounts/auth.py

from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieJWTAuthentication(JWTAuthentication):
    """Allows DRF to read JWT tokens from HttpOnly cookies."""

    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")

        if not access_token:
            return None

        validated_token = self.get_validated_token(access_token)
        return self.get_user(validated_token), validated_token
