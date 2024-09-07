from django.urls import path
from login.views import index,login_user, logout_user,signup, check_login
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', index, name='index'),
    path('signup/', signup, name='signup'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('check_login/', check_login, name='check_login'),  # Check login and redirect
    # path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(next_page=None), name='logout'),  # Logout and redirect to home page
    path('activate/<uidb64>/<token>', views.activate, name='activate')
]