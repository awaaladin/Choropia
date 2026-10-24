from django.urls import path

from .views import (
    GaxtronWebhookView,
    InitializePaymentView,
    PaystackWebhookView,
    VerifyPaymentView,
    WalletSummaryView,
    WalletTransactionsView,
)

urlpatterns = [
    path("payments/initialize/", InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("payments/webhook/gaxtron/", GaxtronWebhookView.as_view(), name="payment-webhook"),
    path("payments/webhook/paystack/", PaystackWebhookView.as_view(), name="payment-webhook-paystack"),
    path("wallet/summary/", WalletSummaryView.as_view(), name="wallet-summary"),
    path("wallet/transactions/", WalletTransactionsView.as_view(), name="wallet-transactions"),
]
