import datetime
import logging

from django import forms
from django.shortcuts import get_object_or_404

from django.contrib.auth import get_user_model
from django.db.models import Q

from coldfront.core.field_of_science.models import FieldOfScience
from coldfront.core.project.models import Project

from cf_plugin_demo.utils import filter_users

# Helper class to create an object to display full name (username)
class FullNameAndUsernameModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() + ' (' + obj.username + ')'

class UsageSearchForm(forms.Form):

    users = FullNameAndUsernameModelMultipleChoiceField(label='Users',
                                                        help_text="""Select users to include in your search. (Max 20)
                                 Project owners can see users on their projects.
                                 Users who do not own a project can only see their own usage.""",
                                                        required=False,
                                                        queryset=None)
    projects = forms.ModelMultipleChoiceField(label='Projects',
                                              help_text='Select projects to include in search',
                                              required=False,
                                              queryset=None)
    pis = FullNameAndUsernameModelMultipleChoiceField(label='PIs',
                                                      help_text="""Select project owners to include in search. 
                                    Project owners can only see their own projects.
                                    """,
                                                      required=False,
                                                      queryset=None)
    field_of_science = forms.ModelMultipleChoiceField(
        help_text="Select fields of study to include",
        label="Field(s) of Study",
        queryset=None,
        required=False)
    start_date = forms.DateField(
        label='Start Date',
        widget=forms.DateInput(attrs={'class': 'datepicker'}, format='%Y-%m-%d'),
        initial=(datetime.date.today() -
                 datetime.timedelta(days=365)).strftime('%Y-%m-%d'),
        required=True)
    end_date = forms.DateField(
        label='End Date',
        widget=forms.DateInput(attrs={'class': 'datepicker'}, format='%Y-%m-%d'),
        initial=datetime.date.today().strftime('%Y-%m-%d'),
        required=True)

    submitted = forms.BooleanField(
        initial=False, required=False, label="submitted")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_obj = user

        # set user specific content
        if user.is_superuser or user.has_perm('project.can_view_all_projects'):
            projects = Project.objects.all().order_by('id').distinct()
        else:
            projects = Project.objects.filter(
                Q(projectuser__user=user)).order_by('id').distinct()

        pi_ids = projects.values_list('pi', flat=True).distinct()
        pis = get_user_model().objects.filter(id__in=pi_ids)

        users = filter_users(user, projects)

        fos_ids = projects.values_list(
            'field_of_science', flat=True).distinct()
        fos = FieldOfScience.objects.filter(id__in=fos_ids)

        self.fields['projects'].queryset = projects.order_by('title')
        self.fields['pis'].queryset = pis.order_by('last_name')
        self.fields['users'].queryset = users.order_by('last_name')
        self.fields['field_of_science'].queryset = fos.order_by('description')

        self.fields["projects"].widget.attrs = {"style": "width:100%;"}
        self.fields["pis"].widget.attrs = {"style": "width:100%;"}
        self.fields["users"].widget.attrs = {"style": "width:100%;"}
        self.fields["field_of_science"].widget.attrs = {"style": "width:100%;"}
        self.fields["submitted"].widget = forms.HiddenInput()
        
        self.fields["projects"].widget["class"] = "fos-select2"
        self.fields["pis"].widget["class"] = "fos-select2"
        self.fields["users"].widget["class"] = "fos-select2"
        self.fields["field_of_science"].widget["class"] = "fos-select2"


    # Enforce a 20 user restriction. This is arbitrary, but doing too big
    # of a query may cause time outs without careful optimizations and caching
    def clean(self):

        cleaned_data = super().clean()
        users = cleaned_data["users"]
        # if len(users) > 20:
        #     raise forms.ValidationError('Cannot select more than 20 users at a time')
        if len(users) == 0:

            if cleaned_data.get('projects'):
                project_list = Project.objects.filter(
                    id__in=self.cleaned_data['projects'])
            else:
                project_list = self.fields['projects'].queryset
            all_users = filter_users(self.user_obj,
                                     project_list,
                                     cleaned_data.get('pis'),
                                     cleaned_data.get('field_of_science'))
            if len(all_users) <= 20:
                cleaned_data["users"] = all_users
            else:
                self.add_error(
                    'users', 'The search is restricted to 20 users, please select up to 20 users to search for or add additional filters to reduce the number of users.')
        return cleaned_data

    # make sure start date is the right format
    def clean_start_date(self):
        try:
            start_date = self.cleaned_data["start_date"]
        except:
            start_date = (datetime.date.today() -
                          datetime.timedelta(days=365)).strftime('%Y-%m-%d')

        return start_date

    # make sure end date is the right format
    def clean_end_date(self):
        try:
            end_date = self.cleaned_data["end_date"]
        except:
            end_date = datetime.date.today().strftime('%Y-%m-%d')

        return end_date