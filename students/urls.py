# students/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('last_login/', views.last_login, name='last_login'),
    path('select_assignments/', views.assignments_page, name='select_assignments'),
    #path('report/<str:assignment_ids>/', views.performance_report, name='performance_report'),
    path('filter/', views.filter_students, name='filter_students'),
    path('send_email/', views.send_email, name='send_email'),
    #path('send_assignment_email/', views.send_assignment_email, name='send_assignment_email'),
]
