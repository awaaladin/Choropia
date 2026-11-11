from django.urls import path

from .payout_views import (
    BanksView,
    CommissionPreviewView,
    FeePreviewView,
    MyPayoutsView,
    PayoutAccountView,
    RunScheduledJobsView,
)
from .views import (
    GaxtronWebhookView,
    InitializePaymentView,
    PaystackWebhookView,
    VerifyPaymentView,
    EscrowMilestoneView,
    WalletSummaryView,
    WalletTransactionsView,
)

urlpatterns = [
    path("payments/initialize/", InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("payments/webhook/gaxtron/", GaxtronWebhookView.as_view(), name="payment-webhook"),
    path("payments/webhook/paystack/", PaystackWebhookView.as_view(), name="payment-webhook-paystack"),
    path("payouts/preview/", CommissionPreviewView.as_view(), name="payout-preview"),
    path("fees/preview/", FeePreviewView.as_view(), name="fee-preview"),
    path("payouts/banks/", BanksView.as_view(), name="payout-banks"),
    path("payouts/account/", PayoutAccountView.as_view(), name="payout-account"),
    path("payouts/", MyPayoutsView.as_view(), name="payouts"),
    path("internal/jobs/run/", RunScheduledJobsView.as_view(), name="run-scheduled-jobs"),
    path("escrow/milestone/", EscrowMilestoneView.as_view(), name="escrow-milestone"),
    path("wallet/summary/", WalletSummaryView.as_view(), name="wallet-summary"),
    path("wallet/transactions/", WalletTransactionsView.as_view(), name="wallet-transactions"),
]
