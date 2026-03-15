from django.urls import path

from .views import index, redirect_short_link

app_name = 'links'

urlpatterns = [
    path('', index, name='index'),
    path('<slug:code>/', redirect_short_link, name='redirect'),
]
