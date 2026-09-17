from django.contrib import admin
from django.urls import include, path

from .health import ready

urlpatterns = [
    path('health/ready/', ready, name='health-ready'),
    path('admin/', admin.site.urls),
    path('', include('links.urls')),
]
