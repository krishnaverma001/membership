# accounts/middleware.py

from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import AnonymousUser

class JWTAuthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith("/admin/"):
            return

        jwt_auth = JWTAuthentication()
        request.user = AnonymousUser()
        access_token = request.COOKIES.get("access_token")
        if access_token:
            try:
                validated_token = jwt_auth.get_validated_token(access_token)
                user = jwt_auth.get_user(validated_token)
                request.user = user
            except Exception:
                pass
