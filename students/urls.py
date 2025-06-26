# students/urls.py

from django.urls import path,include
from . import views

urlpatterns = [
    # in urls.py
path('login/', auth_views.LoginView.as_view(), name='login')
,  # Ensure you have the correct import for auth_views
    path('', views.home, name='home'),
    path('last_login/', views.last_login, name='last_login'),
    path('select_assignments/', views.assignments_page, name='select_assignments'),
    #path('report/<str:assignment_ids>/', views.performance_report, name='performance_report'),
    path('filter/', views.filter_students, name='filter_students'),
    path('send_email/', views.send_email, name='send_email'),
    #path('send_assignment_email/', views.send_assignment_email, name='send_assignment_email'),
]
