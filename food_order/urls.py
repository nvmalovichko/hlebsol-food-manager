from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.MenuView.as_view(), name='menu'),
    url(r'^files/$', views.OrderView.as_view(), name='file_manager'),
    url(r'^week_menu/$', views.MakeOrderView.as_view(), name='order_food'),
    url(r'^ordered_food/$', views.OrderedFoodView.as_view(), name='ordered_food'),
]
