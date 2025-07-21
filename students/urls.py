# students/urls.py

from django.urls import path,include
from . import views
from .views import CustomLoginView
from django.contrib.auth import views as auth_views
from django.views.decorators.csrf import csrf_exempt
urlpatterns = [
    # in urls.py
    path('login/', CustomLoginView.as_view(), name='login'), # Ensure you have the correct import for auth_views
    path('', views.home, name='home'),
    path('last_login/', views.last_login, name='last_login'),
    path('select_assignments/', views.assignments_page, name='select_assignments'),
    #path('report/<str:assignment_ids>/', views.performance_report, name='performance_report'),
    path('filter/', views.filter_students, name='filter_students'),
    path('send_email/', views.send_email, name='send_email'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('send_email_home/', views.send_email_home, name='send_email_home'),
]
