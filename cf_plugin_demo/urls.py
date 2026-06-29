from django.urls import path

from cf_plugin_demo.views import (UserStatsCardView)

urlpatterns = [
    path('stats-cards/', UserStatsCardView.as_view(), name='user-usage-stats')
]