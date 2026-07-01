import datetime
import logging

import pandas as pd
import plotly.graph_objects as go


from django.db.models.query import QuerySet
from django.db.models import Q
from django.contrib.auth import get_user_model
from coldfront.core.project.models import ProjectUser
from coldfront.core.allocation.models import (Allocation)

from coldfront.core.utils.common import import_from_settings

logger = logging.getLogger(__name__)

# Convert types to id lists
def convert_selected_types(selected):
    if isinstance(selected, QuerySet):
        selected = selected.values_list('id', flat=True).distinct()
    else:
        selected = list(map(int, selected))
    return selected

# help function to filter project users
def filter_users(user, projects, pis=[], fos=[]):

    # all possible users
    if pis:
        valid_pis = convert_selected_types(pis)
    else:
        valid_pis = projects.values_list('pi', flat=True)
    if fos:
        valid_fos = convert_selected_types(fos)
    else:
        valid_fos = projects.values_list('field_of_science', flat=True)
    project_users = ProjectUser.objects.prefetch_related(
        'project', 'project__pi', 'project__field_of_science__in',).filter(project__in=projects,
                                                                                                   project__pi__in=valid_pis,
                                                                                                   project__field_of_science__in=valid_fos)
    
    managed_projects = list(projects.filter(Q(pi=user) | (
        Q(projectuser__user=user) & Q(projectuser__role__name='Manager'))))

    # remove users that aren't self if not allowed to view
    if not user.is_superuser and not user.has_perm('project.can_view_all_projects'):
        project_users = project_users.filter(
            Q(user=user) | Q(project__in=managed_projects))

    user_names = list(project_users.values_list(
        'user__username', flat=True).distinct())
    try:
        users = get_user_model().objects.filter(username__in=user_names)
    except Exception as e:
        logger.error('failed to get valid users {}'.format(e))
        users = None
        
    return users

def make_plotly_line(df, key, title, yaxis, xaxis="Date", includejs=False, full_html=False):
    
    # Make a line plot with the provided dataframe columns
    try:

        tmp_plot = go.Figure()
        # add trace for each user
        for user in df['User'].unique():
            tmp_plot.add_trace(go.Scatter(x=df['Date'], y=df[key],
                                        mode='lines+markers',
                                        name=str(user)))
        tmp_plot.update_layout(xaxis_title=xaxis, yaxis_title=yaxis)
        tmp_plot = tmp_plot.to_html(include_plotlyjs=includejs, full_html=full_html, config={'responsive': True})
        
        return tmp_plot
    
    except Exception as e:
        
        logger.error("Failed to make plot with error: {}".format(e))
        return None
    
def get_multiproject_usage_df(projects,
                              start_date,
                              end_date,
                              users_to_include=None,
                              units='day'):
    
    df = None
    
    # Get attribute name from settings or default to slurm_account_name
    COMPUTE_ACCOUNT_ATTRIBUTE_NAME = import_from_settings('CF_PLUGIN_DEMO_COMPUTE_ACCOUNT_ATTRIBUTE_NAME',
                                                          'slurm_account_name')
    # get the file path for the DF from settings
    AGGREGATE_ACCOUNT_DF_PATH = import_from_settings('CF_PLUGIN_DEMO_AGGREGATE_ACCOUNT_DF_PATH')
    
    # can't do anything without a dataframe path
    if not AGGREGATE_ACCOUNT_DF_PATH:
        return df
    
    allocations = Allocation.objects.filter(project__in=projects)
    
    # only deal with compute allocations. You could add features to process other
    # types like storage, licenses, etc.
    compute_allocations = allocations.filter(resources__resource_type__name='Cluster')
    
    # get all the account names
    accounts = []
    for allocation in compute_allocations:
        try:
            account_name = allocation.get_attribute(COMPUTE_ACCOUNT_ATTRIBUTE_NAME)
            accounts.append(account_name)
        except:
            continue
    
    # read in and filter the dataframe
    try:
        df = pd.read_feather(AGGREGATE_ACCOUNT_DF_PATH)
    except Exception as e:
        logger.error('Failed to read dataframe: {}'.format(e))
        return df
    
    mask = (df['Date'] >= pd.Timestamp(start_date, tz="UTC").replace(microsecond=0)) & (
            df['Date'] <= pd.Timestamp(end_date, tz="UTC").replace(microsecond=0))
    mask = mask & (df['Account'].isin(accounts))
    if users_to_include:
        mask = mask & (df['User'].isin(users_to_include))
    df = df[mask].reset_index()
    
    # aggregate to desired units
    # "auto" units
    try:
        delta = end_date - start_date
    except:
        try:
            delta = datetime.datetime.strptime(end_date, '%Y-%m-%d').date() - datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        except Exception as e:
            logger.error("Failed to get time range, defaulting to using units of days: {}".format(e))
            units = 'day'
    if units == 'day':
        freq = 'D'
    elif units == 'month':
        freq = 'MS'
    elif units == 'year':
        freq = 'YS'
    else:
        if delta.days > 1500:
            freq = 'YS'
        elif delta.days > 90:
            freq = 'MS'
        else:
            freq = 'D'
            
    df = df.groupby([pd.Grouper(key='Date', freq=freq), "User"]).agg('sum').reset_index()
    
    return df
    
    
    
        