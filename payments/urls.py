from django.urls import path

from .views import InitializePaymentView, PaystackWebhookView

urlpatterns = [
    path("payments/initialize/", InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/webhook/paystack/", PaystackWebhookView.as_view(), name="payment-webhook"),
]
