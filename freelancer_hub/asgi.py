import os
import django
import asyncio
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freelancer_hub.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import core.routing
import client.routing
import freelancer.routing
import chat.routing

# Set the event loop policy to use a more scalable reactor
if sys.platform == 'linux':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                core.routing.websocket_urlpatterns + 
                client.routing.websocket_urlpatterns +
                freelancer.routing.websocket_urlpatterns +
                chat.routing.websocket_urlpatterns
            )
        )
    ),
})
