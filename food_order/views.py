import datetime
import itertools
import os
import urllib.parse
import xlrd
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.views.generic.base import TemplateView
from xlutils.copy import copy as xlutils_copy

import hlebsol.settings
from .forms import MenuFileForm
from .models import MenuItem, Category, MenuFile, FoodOffer, LiveSetting

XLS_NCOLUMNS_MAP = dict(
    quantity=4,
    position_sum_price=5,
    total_price=5,
    total_price_string=4,
)


def toggle_block_order(request):
    if request.method == 'POST':
        block_order = LiveSetting.get_setting(name='block_order')
        if block_order.value == 'true':
            block_order.value = 'false'
        else:
            block_order.value = 'true'
        block_order.save()
    return HttpResponseRedirect(reverse('file_manager'))


class MenuView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    redirect_field_name = ''
    template_name = 'food_order/menu.html'


class OrderView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    redirect_field_name = ''
    template_name = 'food_order/file_manager.html'

    def get_context_data(self, **kwargs):
        context = dict(
            form=MenuFileForm,
            menus=MenuFile.objects.all(),
        )
        if LiveSetting.get_setting('block_order').value == 'true':
            context['block_order_status'] = True
        return context

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
                    category_counter = 1
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
                            category_name = '{}. {}'.format(category_counter, row[0].value)
                            category, created = Category.objects.get_or_create(name=category_name)
                            category_counter += 1
                        else:  # menu item getter
                            menu_date = datetime.datetime.strptime(sheet.name.split()[0], '%d.%m.%y')
                            MenuItem.objects.update_or_create(
                                nrow=irow,
                                position=row[0].value,
                                name=row[1].value,
                                mass=row[2].value,
                                price=row[3].value,
                                menu_day=sheet.name,
                                menu_date=menu_date,
                                category=category,
                                defaults={'from_file': menu_file}
                            )
        elif request.POST['file_action'] == 'export':
            form = MenuFileForm(request.POST, request.FILES)
            if form.is_valid():
                filename = request.FILES['menu_file'].name
                filedata = request.FILES['menu_file'].read()
                filepath = urllib.parse.urljoin(hlebsol.settings.MEDIA_ROOT, filename)
                with open(filepath, 'wb') as f:
                    f.write(filedata)
                rb = xlrd.open_workbook(filepath, formatting_info=True)
                wb = xlutils_copy(rb)

                # prepare data
                menu_file = MenuFile.get_latest()
                food_offers_list = (
                    FoodOffer.objects
                        .filter(menu_item__from_file=menu_file)
                        .values('menu_item__nrow', 'menu_item__menu_day', 'menu_item__price')
                        .annotate(total_quantity=Sum('quantity'))
                )
                food_offers_list = (
                    (agg['menu_item__menu_day'], agg['menu_item__nrow'], agg['menu_item__price'], agg['total_quantity'])
                    for agg in food_offers_list
                )
                food_offers_group_gen = itertools.groupby(sorted(food_offers_list, key=lambda x: x[0]), lambda x: x[0])

                # update all ordered positions: quantity and price
                for sheet_name, values in food_offers_group_gen:
                    total_price = 0
                    # get target sheet
                    sheet = wb.get_sheet(sheet_name)
                    # find 'ВСЕГО' row number in sheet
                    total_price_nrow = self._get_total_price_nrow(rb.sheet_by_name(sheet_name))
                    for _, nrow, price, total_quantity in values:
                        # write total quantity for specific position by row
                        sheet.write(nrow, XLS_NCOLUMNS_MAP['quantity'], total_quantity)
                        # calculate and write sum price for specific position by row
                        position_sum_price = price * total_quantity
                        total_price += position_sum_price
                        sheet.write(nrow, XLS_NCOLUMNS_MAP['position_sum_price'], position_sum_price)
                    # write total price for target sheet
                    sheet.write(total_price_nrow, XLS_NCOLUMNS_MAP['total_price'], total_price)

                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename=mercaux_menu.xls'
                wb.save(response)
                return response
        return HttpResponseRedirect(request.path)

    @staticmethod
    def _get_total_price_nrow(sheet):
        for irow in range(sheet.nrows):
            row = sheet.row(irow)
            row_value = row[XLS_NCOLUMNS_MAP['total_price_string']].value.strip()
            if row_value == 'ВСЕГО:':
                return irow
        raise ValueError("Menu export failure: can't find total price string")


class MakeOrderView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    redirect_field_name = ''
    template_name = 'food_order/order.html'

    def get(self, request, *args, **kwargs):
        kwargs['user'] = request.user
        kwargs['day_page'] = request.POST.get('page_number') or request.GET.get('day_page', 1)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        day_date = datetime.datetime.strptime(request.POST['day_date'], '%d.%m.%y')

        # Check if user already made an order for this day
        if FoodOffer.order_exists(user=request.user, day_date=day_date):
            return self.get(request, *args, **kwargs)

        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        assert len(product_ids) == len(quantities)
        food_quantities = [FoodOffer(menu_item_id=product_id, quantity=quantity, user=request.user) for
                           product_id, quantity in zip(product_ids, quantities) if quantity not in ('', '0')]

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
            day_date=day_date.strftime('%d.%m.%y'),
            day_name=day_name,
        )
        already_ordered = FoodOffer.order_exists(user=user, day_date=day_date)
        order_blocked = LiveSetting.get_setting('block_order').value == 'false'
        if order_blocked:
            context['block_order_status'] = True
        if already_ordered:
            context['already_ordered'] = True
        return context


class OrderedFoodView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    redirect_field_name = ''
    template_name = 'food_order/ordered_food.html'

    def get(self, request, *args, **kwargs):
        kwargs['all_users'] = request.GET.get('all_users')
        kwargs['user'] = request.user
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = dict(
            orders=FoodOffer.collect_recent_orders(kwargs['user'], kwargs['all_users']),
        )
        return context


class AnnulledOrder(LoginRequiredMixin, TemplateView):
    login_url = '/login/'

    def post(self, request, *args, **kwargs):
        day_date = datetime.datetime.strptime(request.POST['day_date'], '%d.%m.%y')
        page_number = request.POST['page_number']

        FoodOffer.objects.filter(user=request.user, menu_item__menu_date=day_date).delete()

        return HttpResponseRedirect(f'{reverse("order_food")}?day_page={page_number}')
