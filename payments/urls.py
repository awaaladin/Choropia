from django.urls import path

from .views import GaxtronWebhookView, InitializePaymentView

urlpatterns = [
    path("payments/initialize/", InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/webhook/gaxtron/", GaxtronWebhookView.as_view(), name="payment-webhook"),
]
