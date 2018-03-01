# Generated by Django 2.0.2 on 2018-02-15 08:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name='FoodOffer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField()),
                ('updated_dt', models.DateTimeField(auto_now=True)),
                ('created_dt', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='MenuFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upload', models.FileField(db_index=True, upload_to='uploads/')),
                ('created_dt', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='MenuItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nrow', models.IntegerField()),
                ('position', models.IntegerField()),
                ('name', models.CharField(max_length=255)),
                ('mass', models.CharField(max_length=32, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=5)),
                ('menu_day', models.CharField(max_length=64)),
                ('menu_date', models.DateField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='food_order.Category')),
                ('from_file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='menu_items', to='food_order.MenuFile')),
            ],
        ),
        migrations.AddField(
            model_name='foodoffer',
            name='menu_item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='food_offers', to='food_order.MenuItem'),
        ),
        migrations.AddField(
            model_name='foodoffer',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_food_offers', to=settings.AUTH_USER_MODEL),
        ),
    ]