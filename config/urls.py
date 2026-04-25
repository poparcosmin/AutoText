"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from textsync.views.health import privacy_view, help_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('textsync.urls')),
    path('tinymce/', include('tinymce.urls')),
    path('privacy.html', privacy_view, name='privacy'),
    path('help', help_view, name='help'),
    path('help/', help_view),  # tolerate trailing slash
]

# django-silk profiling dashboard — enabled via ENABLE_SILK env var
if 'silk' in settings.INSTALLED_APPS:
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
