import itertools

from django.contrib.auth.models import User
from django.db import models


class MenuFile(models.Model):
    upload = models.FileField(db_index=True, upload_to='uploads/')

    created_dt = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_latest(cls):
        return cls.objects.latest('created_dt')


class Category(models.Model):
    name = models.CharField(db_index=True, max_length=128)


class MenuItem(models.Model):
    nrow = models.IntegerField()
    position = models.IntegerField()
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    mass = models.CharField(max_length=32, null=True)
    price = models.DecimalField(max_digits=5, decimal_places=2)
    menu_day = models.CharField(max_length=64)
    menu_date = models.DateField(null=False)
    from_file = models.ForeignKey(MenuFile, on_delete=models.CASCADE, related_name='menu_items')

    @classmethod
    def get_last_menu_days(cls, menu_file_id):
        return sorted({d for d in MenuItem.objects.filter(from_file_id=menu_file_id)
                      .values_list('menu_day', 'menu_date')}, key=lambda x: x[1])

    @classmethod
    def collect_menu(cls, menu_file_id, menu_date):
        menu_items = cls.objects.filter(menu_date=menu_date, from_file_id=menu_file_id).select_related('category')
        return {category: list(positions) for category, positions in
                itertools.groupby(menu_items, lambda x: x.category.name)}


class FoodOffer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_food_offers')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='food_offers')
    quantity = models.IntegerField(null=False)

    updated_dt = models.DateTimeField(auto_now=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    @classmethod
    def order_exists(cls, user, day_date):
        return cls.objects.filter(user=user, menu_item__menu_date=day_date).exists()
