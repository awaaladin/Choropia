from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/code/", views.login_code_view, name="login_code"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("payouts/", views.payout_list, name="payout_list"),
    path("payouts/<int:pk>/", views.payout_detail, name="payout_detail"),
    path("payouts/<int:pk>/reveal/", views.payout_reveal, name="payout_reveal"),
    path("payouts/<int:pk>/mark-paid/", views.payout_mark_paid, name="payout_mark_paid"),
    path("payouts/<int:pk>/retry/", views.payout_retry, name="payout_retry"),
    path("money/", views.money, name="money"),
    path("money/payouts.csv", views.payouts_csv, name="payouts_csv"),
    path("deals/", views.deals, name="deals"),
    path("sellers/", views.sellers, name="sellers"),
    path("sellers/add/", views.seller_add, name="seller_add"),
    path("sellers/<int:pk>/remove/", views.seller_remove, name="seller_remove"),
    path("sellers/setting/", views.seller_setting, name="seller_setting"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/resolve/", views.order_resolve, name="order_resolve"),
    path("drivers/", views.driver_list, name="driver_list"),
    path("drivers/<int:pk>/", views.driver_detail, name="driver_detail"),
    path("drivers/<int:pk>/decide/", views.driver_decide, name="driver_decide"),
    path("drivers/<int:pk>/test/", views.driver_test_toggle, name="driver_test_toggle"),
    path("documents/<int:pk>/", views.document_view, name="document_view"),
    path("people/", views.user_list, name="user_list"),
    path("people/<int:pk>/", views.user_detail, name="user_detail"),
    path("people/<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
    path("listings/", views.listing_list, name="listing_list"),
    path("listings/<int:pk>/toggle/", views.listing_toggle, name="listing_toggle"),
    path("audit/", views.audit_log, name="audit"),
    path("keys/", views.key_backup, name="key_backup"),
    path("keys/create/", views.key_backup_create, name="key_backup_create"),
    path("keys/recover/", views.key_backup_recover, name="key_backup_recover"),
]
