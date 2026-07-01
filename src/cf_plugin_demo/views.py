import datetime
import logging
import json
import math

import pandas as pd

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core import serializers
from django.shortcuts import get_object_or_404, redirect, render


from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project

from cf_plugin_demo.forms import UsageSearchForm
from cf_plugin_demo.utils import filter_users, make_plotly_line, get_multiproject_usage_df

logger = logging.getLogger(__name__)

class UserStatsCardView(LoginRequiredMixin, TemplateView):

    template_name = 'cf_plugin_demo/user_stat_cards.html'
    context_object_name = 'stats_cards'

    def get_queryset(self):

        user = self.request.user
        
        # filter projects the user is allowed to view
        # Let SuperUser of anyone with view all permissions see all
        # otherwise only let users see projects they are on
        if user.is_superuser or user.has_perm('project.can_view_all_projects'):
            projects = Project.objects.all().order_by('id')
        else:
            projects = Project.objects.filter(
                Q(projectuser__user=user)
            ).order_by('id')

        return projects.distinct()

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        return context

    def get(self, request, *args, **kwargs):

        context = self.get_context_data(**kwargs)
        project_list = self.get_queryset()
        usage_search_form = UsageSearchForm(
            self.request.user, self.request.GET)
        selected_projects = self.request.GET.getlist("selected_projects[]")
        selected_pis = self.request.GET.getlist("selected_pis[]")
        selected_fos = self.request.GET.getlist("selected_fos[]")

        does_req_accept_json = self.request.accepts("application/json")
        is_ajax_request = self.request.headers.get(
            "x-requested-with") == "XMLHttpRequest" and does_req_accept_json

        # only process if searched
        if "submitted" in usage_search_form.data:
            if usage_search_form.is_valid():
                context['usage_search_form'] = usage_search_form
                data = usage_search_form.cleaned_data
                if data['projects']:
                    project_list = project_list.filter(id__in=data['projects'])
                if data['pis']:
                    project_list = project_list.filter(pi__in=data['pis'])
                if data['field_of_science']:
                    project_list = project_list.filter(
                        field_of_science__in=data['field_of_science'])
                if data['users']:
                    user_list = [user.username for user in data['users']]
                else:
                    # all valid users
                    try:
                        users = filter_users(self.request.user,
                                            project_list,
                                            data['pis'],
                                            data['field_of_science'])

                        user_list = [user.username for user in users]
                    except Exception as e:
                        logger.error(
                            "Failed to filter user with error: {}".format(e))
                        user_list = [request.user.username]

                # filter searched projects to only include those with users
                project_list = project_list.filter(
                    projectuser__user__username__in=user_list)

                projects_count = project_list.count()
                context['projects_count'] = projects_count

                try:
                    df = get_multiproject_usage_df(project_list,
                                                   data['start_date'],
                                                   data['end_date'],
                                                   users_to_include=user_list)
                    print(df)
                except Exception as e:
                    logger.error(
                        "failed to get usage df with error: {}".format(e))
                    df = pd.DataFrame()

                # create dict of usage
                usage_dict = []
                compute_allocations = Allocation.objects.filter(
                    project__in=project_list, resources__resource_type__name='Cluster')
                storage_allocations = Allocation.objects.filter(
                    project__in=project_list, resources__resource_type__name='Storage')

                # we only need to include the plotly js once no matter
                # how many plots are generated
                include_plotlyjs = True
                
                # define plot types
                plot_types = {
                    "CPU Hours": {
                        "title": "CPU Usage (CPU Hours)",
                        "yaxis": "CPU Hours",
                        "plot_name": "cpu_plot",
                        "count_name": "cpu_total"
                    },
                    "GPU Hours": {
                        "title": "GPU Usage (GPU Hours)",
                        "yaxis": "GPU Hours",
                        "plot_name": "gpu_plot",
                        "count_name": "gpu_total"
                    },
                    "Memory Hours": {
                        "title": "Memory Usage (GB Hours)",
                        "yaxis": "GB Hours",
                        "plot_name": "mem_plot",
                        "count_name": "mem_total"
                    }
                }
                
                # loop over users and general plots
                for user in data['users']:
                    
                    # data available directly from projects and allocations
                    tmp_entry = {
                        "name": user.get_full_name(),
                        "num_projects": project_list.filter(Q(projectuser__user=user)).distinct().count(),
                        "num_compute_allocations": compute_allocations.filter(Q(allocationuser__user=user)).distinct().count(),
                        "num_storage_allocations": storage_allocations.filter(Q(allocationuser__user=user)).distinct().count()
                    }
                    
                    # Add job data, if available
                    mask = df['User'] == str(user.username)
                    user_df = df[mask]
                    
                    if df.empty:
                        
                        # set all the plot types to none and the counts to 0
                        for key, values in plot_types.items():
                            tmp_entry[values['plot_name']] = None
                            tmp_entry[values['count_name']] = 0
                    
                    else:
                        
                        # try to generate the requested plots
                        for key, values in plot_types.items():
                            
                            tmp_entry[values['count_name']] = round(user_df[key].sum())
                            tmp_entry[values['plot_name']] = make_plotly_line(user_df, key, values['title'], values['yaxis'], includejs=include_plotlyjs)
                            
                            # only need to include js once
                            include_plotlyjs = False
                            
                    usage_dict.append(tmp_entry)

                context['stats_cards'] = usage_dict
                context['stats_cards_count'] = len(usage_dict)

                context['begin_date'] = data['start_date']
                context['end_date'] = data['end_date']
                context['expand_accordion'] = 'hide'
                
                print(json.dumps(usage_dict, indent=2))

            else:
                project_list = None
                for error in usage_search_form.errors:
                    messages.error(self.request, error)

                context['usage_search_form'] = usage_search_form
                context['expand_accordion'] = 'show'
        else:
            search_form = UsageSearchForm(self.request.user)

            if is_ajax_request and selected_projects:
                project_list = project_list.filter(id__in=selected_projects)

            # update allowed users
            try:
                users = filter_users(self.request.user,
                                     project_list,
                                     selected_pis,
                                     selected_fos)
            except Exception as e:
                users = [self.request.user]
                logger.error('Failed to get allowed users: {}'.format(e))

            context['usage_search_form'] = search_form
            context['expand_accordion'] = 'show'
            projects_count = project_list.count()
            context['projects_count'] = projects_count

            if is_ajax_request:
                json_users = serializers.serialize(
                    'json', users, fields=['pk', 'first_name', 'last_name', 'username'])
                json_context = {'user_query': json_users}

                return JsonResponse(data=json_context, safe=False)

        return render(request, self.template_name, context)