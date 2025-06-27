"""
URL configuration for freelancer_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from rest_framework import routers
from drf_yasg.views import get_schema_view
from django.conf.urls.static import static
from django.conf import settings
from drf_yasg import openapi
from django.conf import settings
from django.conf.urls.static import static
from OBSP.views import *


schema_view = get_schema_view(
   openapi.Info(
      title="Freelancer Collaboration Hub API",
      default_version='v1',
      description="API documentation for Freelancer Collaboration Hub",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@freelancerhub.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
)

# Customize admin site
admin.site.site_header = "Talintz Admin"
admin.site.site_title = "Talintz Admin Portal"
admin.site.index_title = "Welcome to Talintz Administration"

# API URL routing
urlpatterns = [
    path('api/', include('core.urls')),
    path('api/client/', include('client.urls')),
    path('api/finance/', include('financeapp.urls')),
    path('api/freelancer/', include('freelancer.urls')),
    path('admin/', admin.site.urls),
    path('admin/obsp/preview/<int:obsp_id>/', obsp_preview, name='obsp_preview'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-docs'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc-docs'),
    path('api/obsp/', include('OBSP.urls')),
    path('api/chat/', include('chat.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 