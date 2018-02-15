from django import forms

class MenuFileForm(forms.Form):
    menu_file = forms.FileField(
        label='Select a file',
        help_text='max. 42 megabytes'
    )