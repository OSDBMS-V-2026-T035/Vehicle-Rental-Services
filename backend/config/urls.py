"""URL configuration for the Vehicle Rental Services project."""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from apps.accounts.views import auth_page, login_view, logout_view, send_otp_view, signup_view


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("auth/", auth_page, name="auth"),
    path("api/auth/login/", login_view, name="api-login"),
    path("api/auth/logout/", logout_view, name="api-logout"),
    path("api/auth/signup/", signup_view, name="api-signup"),
    path("api/auth/send-otp/", send_otp_view, name="api-send-otp"),
    path("admin/", admin.site.urls),
]
