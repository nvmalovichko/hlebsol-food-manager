import datetime
import os

from xlutils.copy import copy as xlutils_copy
import hlebsol.settings
import xlrd
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.views.generic.base import TemplateView

from .forms import MenuFileForm
from .models import MenuItem, Category, MenuFile, FoodOffer


class OrderView(TemplateView):
    template_name = 'food_order/order.html'

    def get_context_data(self, **kwargs):
        return dict(form=MenuFileForm, menus=MenuFile.objects.all())

    @transaction.atomic
    def post(self, request):

        if request.POST['file_action'] == 'import':
            form = MenuFileForm(request.POST, request.FILES)
            if form.is_valid():
                # upload menu
                menu_file = MenuFile(upload=request.FILES['menu_file'])
                menu_file.save()
                # read xls
                new_filepath = os.path.join(hlebsol.settings.MEDIA_ROOT, menu_file.upload.url)
                wb = xlrd.open_workbook(filename=new_filepath)
                for sheet in wb.sheets():
                    continue_flag = True
                    category = 'Неизвестно'
                    for irow in range(sheet.nrows):
                        # search for start
                        row = sheet.row(irow)
                        if row[1].value == 'Наименование':
                            continue_flag = False
                            continue
                        elif not any([row[0].value, row[1].value, row[2].value, row[3].value]):
                            continue_flag = True

                        if continue_flag:
                            continue

                        if row[0].ctype == 1:  # Category getter
                            category, created = Category.objects.get_or_create(name=row[0].value)
                        else:  # menu item getter
                            menu_date = datetime.datetime.strptime(sheet.name.split()[0], '%d.%m.%y')
                            try:
                                menu_item = MenuItem.objects.get(nrow=irow,
                                                                 position=row[0].value,
                                                                 name=row[1].value,
                                                                 mass=row[2].value,
                                                                 price=row[3].value,
                                                                 menu_day=sheet.name,
                                                                 menu_date=menu_date,
                                                                 category=category)
                                menu_item.from_file = menu_file
                                menu_item.save()
                            except MenuItem.DoesNotExist:
                                MenuItem.objects.create(nrow=irow,
                                                        position=row[0].value,
                                                        name=row[1].value,
                                                        mass=row[2].value,
                                                        price=row[3].value,
                                                        menu_day=sheet.name,
                                                        menu_date=menu_date,
                                                        category=category,
                                                        from_file=menu_file)
        elif request.POST['file_action'] == 'export':
            menu_file = MenuFile.get_latest()
            food_offers_list = (
                FoodOffer.objects
                    .filter(menu_item__from_file=menu_file)
                    .values('menu_item__nrow', 'menu_item__menu_day')
                    .annotate(total_quantity=Sum('quantity'))
            )
            food_offers_list = ((agg['menu_item__nrow'], agg['menu_item__menu_day'], agg['total_quantity'])
                                for agg in food_offers_list)

            filepath = os.path.join(hlebsol.settings.MEDIA_ROOT, menu_file.upload.url)
            rb = xlrd.open_workbook(filepath)
            wb = xlutils_copy(rb)

            for nrow, sheet_name, total_quantity in food_offers_list:
                s = wb.get_sheet(sheet_name)
                s.write(nrow, 4, total_quantity)
            wb.save('test.xls')

        return HttpResponseRedirect(request.path)


class MenuView(TemplateView):
    template_name = 'food_order/menu.html'

    def get(self, request, *args, **kwargs):
        kwargs['user'] = request.user
        kwargs['day_page'] = request.POST.get('page_number') or request.GET.get('day_page', 1)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        day_date = datetime.datetime.strptime(request.POST['day_date'], '%d.%m.%y')
        if FoodOffer.order_exists(user=request.user, day_date=day_date):
            return self.get(request, *args, **kwargs)

        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        assert len(product_ids) == len(quantities)
        food_quantities = [FoodOffer(menu_item_id=product_id, quantity=quantity, user=request.user) for
                           product_id, quantity in zip(product_ids, quantities) if quantity]

        FoodOffer.objects.bulk_create(food_quantities)
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        file_id = MenuFile.get_latest().id
        recent_week_days = MenuItem.get_last_menu_days(file_id)
        user = kwargs.get('user')

        day_paginator = Paginator(recent_week_days, 1)
        day_page_number = kwargs.get('day_page')
        day_page = day_paginator.page(int(day_page_number))
        day_name, day_date = day_page.object_list[0]

        context = dict(
            day_page=day_page,
            menu=MenuItem.collect_menu(file_id, day_date),
            user=user,
            day_date=day_date.strftime('%d.%m.%y'),
            day_name=day_name,
        )
        if FoodOffer.order_exists(user=user, day_date=day_date):
            context['is_already_ordered'] = True
        return context
