from django import forms
from .models import Assignment

class StudentFilterForm(forms.Form):
    section = forms.MultipleChoiceField(choices=[], required=False, widget=forms.SelectMultiple)
    assignments = forms.ModelMultipleChoiceField(queryset=Assignment.objects.all(), required=False, widget=forms.SelectMultiple)
    status = forms.ChoiceField(choices=[('all', 'All')] + [(status, status) for status in Assignment.objects.values_list('status', flat=True).distinct()], required=False)

    def __init__(self, *args, **kwargs):
        sections = kwargs.pop('sections', [])
        statuses = kwargs.pop('statuses', [])
        super(StudentFilterForm, self).__init__(*args, **kwargs)
        self.fields['section'].choices = [(section, section) for section in sections]
        self.fields['status'].choices = [('all', 'All')] + [(status, status) for status in statuses]
