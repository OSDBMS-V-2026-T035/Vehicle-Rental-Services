"""URL configuration for the Vehicle Rental Services project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from apps.accounts.views import auth_page, booking_checkout_page, captcha_view, customer_profile_view, login_view, logout_view, password_reset_confirm_view, password_reset_otp_view, portal_view, send_otp_view, signup_view, update_customer_profile_view, verify_signup_otp_view
from apps.adminpanel.views import booking_action, shopkeeper_action, user_action, vehicle_action
from apps.adminpanel.portal_views import admin_audit, admin_catalog, admin_commission_configuration, admin_earnings, admin_revenue, admin_review_queues, admin_summary
from apps.bookings.views import booking_history, cancel_customer_booking, checkout_defaults, create_booking, create_checkout_booking_view, request_handover_code, shopkeeper_vehicle_availability
from apps.bookings.documents import download_booking_document
from apps.accounts.shopkeeper_portal_views import set_vehicle_availability, shopkeeper_earnings, shopkeeper_reservation_action, shopkeeper_reservations, shopkeeper_summary, update_vehicle_rate
from apps.payments.views import create_razorpay_order, razorpay_checkout_status, razorpay_webhook, reconcile_razorpay_payment, verify_razorpay_payment
from apps.shops.views import search_shops, shopkeeper_dashboard, update_shopkeeper_profile
from apps.vehicles.views import create_vehicle, my_vehicles, remove_vehicle, search_vehicles, update_vehicle_inventory, vehicle_detail


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("auth/", auth_page, name="auth"),
    path("api/auth/captcha/", captcha_view, name="api-captcha"),
    path("api/auth/login/", login_view, name="api-login"),
    path("api/auth/logout/", logout_view, name="api-logout"),
    path("api/auth/signup/", signup_view, name="api-signup"),
    path("api/auth/send-otp/", send_otp_view, name="api-send-otp"),
    path("api/auth/verify-otp/", verify_signup_otp_view, name="api-verify-signup-otp"),
    path("api/auth/password-reset/send-otp/", password_reset_otp_view, name="api-password-reset-otp"),
    path("api/auth/password-reset/confirm/", password_reset_confirm_view, name="api-password-reset-confirm"),
    path("api/customer/profile/", customer_profile_view, name="customer-profile"),
    path("api/customer/profile/update/", update_customer_profile_view, name="customer-profile-update"),
    # The legacy template combined every admin operation into one long page.
    # Use the protected portal shell instead; its dedicated hash routes keep
    # shopkeepers, vehicles, bookings, customers, finance, and audit separate.
    path("control-panel/", portal_view, {"portal_role": "ADMIN"}, name="admin-portal"),
    path("api/admin/shopkeepers/<int:profile_id>/action/", shopkeeper_action, name="admin-shopkeeper-action"),
    path("api/admin/summary/", admin_summary, name="admin-summary"),
    path("api/admin/review-queues/", admin_review_queues, name="admin-review-queues"),
    path("api/admin/audit/", admin_audit, name="admin-audit"),
    path("api/admin/earnings/", admin_earnings, name="admin-earnings"),
    path("api/admin/revenue/", admin_revenue, name="admin-revenue"),
    path("api/admin/commission/", admin_commission_configuration, name="admin-commission"),
    path("api/admin/catalog/<str:resource>/", admin_catalog, name="admin-catalog"),
    path("api/admin/vehicles/<int:vehicle_id>/action/", vehicle_action, name="admin-vehicle-action"),
    path("api/admin/users/<int:user_id>/action/", user_action, name="admin-user-action"),
    path("api/admin/bookings/<int:booking_id>/action/", booking_action, name="admin-booking-action"),
    # The shopkeeper workspace uses the same route-driven portal shell as the
    # customer and admin workspaces. Each sidebar item replaces the content
    # view, so profile/fleet/bookings do not become one long page.
    path("shopkeeper/", portal_view, {"portal_role": "SHOPKEEPER"}, name="shopkeeper-portal"),
    path("shopkeeper/<str:section>/", portal_view, {"portal_role": "SHOPKEEPER"}, name="shopkeeper-portal-section"),
    path("user-portal/", portal_view, {"portal_role": "USER"}, name="user-portal"),
    path("user-portal/<str:section>/", portal_view, {"portal_role": "USER"}, name="user-portal-section"),
    path("booking/checkout/", booking_checkout_page, name="booking-checkout-page"),
    path("control-panel/<str:section>/", portal_view, {"portal_role": "ADMIN"}, name="admin-portal-section"),
    path("api/shopkeeper/profile/", update_shopkeeper_profile, name="shopkeeper-profile-update"),
    path("api/shopkeeper/summary/", shopkeeper_summary, name="shopkeeper-summary"),
    path("api/shopkeeper/reservations/", shopkeeper_reservations, name="shopkeeper-reservations"),
    path("api/shopkeeper/earnings/", shopkeeper_earnings, name="shopkeeper-earnings"),
    path("api/shopkeeper/reservations/<int:booking_id>/action/", shopkeeper_reservation_action, name="shopkeeper-reservation-action"),
    path("api/shopkeeper/vehicles/<int:vehicle_id>/availability/", set_vehicle_availability, name="shopkeeper-vehicle-availability"),
    path("api/shopkeeper/vehicles/<int:vehicle_id>/rate/", update_vehicle_rate, name="shopkeeper-vehicle-rate"),
    path("api/shopkeeper/vehicles/<int:vehicle_id>/inventory/", update_vehicle_inventory, name="shopkeeper-vehicle-inventory"),
    path("api/shopkeeper/vehicles/", my_vehicles, name="shopkeeper-vehicles"),
    path("api/shopkeeper/vehicles/create/", create_vehicle, name="vehicle-create"),
    path("api/shopkeeper/vehicles/<int:vehicle_id>/remove/", remove_vehicle, name="vehicle-remove"),
    path("api/shops/search/", search_shops, name="shops-search"),
    path("api/vehicles/search/", search_vehicles, name="vehicles-search"),
    path("api/vehicles/<int:vehicle_id>/", vehicle_detail, name="vehicle-detail"),
    path("api/bookings/", create_booking, name="booking-create"),
    path("api/bookings/checkout/", create_checkout_booking_view, name="booking-checkout"),
    path("api/bookings/checkout/defaults/", checkout_defaults, name="booking-checkout-defaults"),
    path("api/bookings/history/", booking_history, name="booking-history"),
    path("api/bookings/<int:booking_id>/handover-code/", request_handover_code, name="booking-handover-code"),
    path("api/bookings/<int:booking_id>/documents/<str:kind>/", download_booking_document, name="booking-document-download"),
    path("api/bookings/<int:booking_id>/cancel/", cancel_customer_booking, name="booking-cancel"),
    path("api/payments/razorpay/order/<int:payment_id>/", create_razorpay_order, name="razorpay-create-order"),
    path("api/payments/razorpay/status/", razorpay_checkout_status, name="razorpay-checkout-status"),
    path("api/payments/razorpay/verify/", verify_razorpay_payment, name="razorpay-verify-payment"),
    path("api/payments/razorpay/reconcile/<int:payment_id>/", reconcile_razorpay_payment, name="razorpay-reconcile-payment"),
    path("api/payments/razorpay/webhook/", razorpay_webhook, name="razorpay-webhook"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




