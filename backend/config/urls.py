"""URL configuration for the Vehicle Rental Services project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from apps.accounts.views import auth_page, login_view, logout_view, send_otp_view, signup_view
from apps.adminpanel.views import dashboard as admin_dashboard, shopkeeper_action, user_action, vehicle_action
from apps.bookings.views import booking_history, create_booking
from apps.shops.views import search_shops, shopkeeper_dashboard, update_shopkeeper_profile
from apps.vehicles.views import create_vehicle, my_vehicles, search_vehicles


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("auth/", auth_page, name="auth"),
    path("api/auth/login/", login_view, name="api-login"),
    path("api/auth/logout/", logout_view, name="api-logout"),
    path("api/auth/signup/", signup_view, name="api-signup"),
    path("api/auth/send-otp/", send_otp_view, name="api-send-otp"),
    path("control-panel/", admin_dashboard, name="custom-admin-dashboard"),
    path("api/admin/shopkeepers/<int:profile_id>/action/", shopkeeper_action, name="admin-shopkeeper-action"),
    path("api/admin/vehicles/<int:vehicle_id>/action/", vehicle_action, name="admin-vehicle-action"),
    path("api/admin/users/<int:user_id>/action/", user_action, name="admin-user-action"),
    path("shopkeeper/", shopkeeper_dashboard, name="shopkeeper-dashboard"),
    path("api/shopkeeper/profile/", update_shopkeeper_profile, name="shopkeeper-profile-update"),
    path("api/shopkeeper/vehicles/", my_vehicles, name="shopkeeper-vehicles"),
    path("api/shopkeeper/vehicles/create/", create_vehicle, name="vehicle-create"),
    path("api/shops/search/", search_shops, name="shops-search"),
    path("api/vehicles/search/", search_vehicles, name="vehicles-search"),
    path("api/bookings/", create_booking, name="booking-create"),
    path("api/bookings/history/", booking_history, name="booking-history"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
