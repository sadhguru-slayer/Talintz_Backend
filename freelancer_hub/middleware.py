from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware  # Correct import
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from core.models import User  # Ensure your User model is correct

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope["query_string"].decode()
        query_params = parse_qs(query_string)

        token = query_params.get("token", [None])[0]  # Get token from URL
        scope["user"] = AnonymousUser()  # Default to anonymous
        if token:
            try:
                access_token = AccessToken(token)  # Validate JWT
                user = await sync_to_async(User.objects.get)(id=access_token["user_id"])
                scope["user"] = user  # Attach user to scope
            except Exception as e:
                print(f"JWT Authentication Failed: {e}")

        return await super().__call__(scope, receive, send)
