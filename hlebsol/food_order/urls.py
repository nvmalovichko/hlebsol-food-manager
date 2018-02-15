from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.OrderView.as_view(), name='order'),
    url(r'week_menu/', views.MenuView.as_view(), name='week_menu'),
]
