from django.urls import path

from .views import GaxtronWebhookView, InitializePaymentView, WalletSummaryView, WalletTransactionsView

urlpatterns = [
    path("payments/initialize/", InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/webhook/gaxtron/", GaxtronWebhookView.as_view(), name="payment-webhook"),
    path("wallet/summary/", WalletSummaryView.as_view(), name="wallet-summary"),
    path("wallet/transactions/", WalletTransactionsView.as_view(), name="wallet-transactions"),
]
