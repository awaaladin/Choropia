from django.urls import path

from .views import (
    CancelOfferView,
    ConfirmHandoverView,
    ConversationOffersView,
    DeclineOfferView,
    HandoverCodeView,
    OfferCheckoutView,
    OfferDetailView,
    VerifyOfferPaymentView,
)

urlpatterns = [
    path("conversations/<int:conversation_id>/offers/", ConversationOffersView.as_view(), name="conversation-offers"),
    path("offers/<uuid:offer_id>/", OfferDetailView.as_view(), name="offer-detail"),
    path("offers/<uuid:offer_id>/cancel/", CancelOfferView.as_view(), name="offer-cancel"),
    path("offers/<uuid:offer_id>/decline/", DeclineOfferView.as_view(), name="offer-decline"),
    path("offers/<uuid:offer_id>/checkout/", OfferCheckoutView.as_view(), name="offer-checkout"),
    path("offers/<uuid:offer_id>/verify-payment/", VerifyOfferPaymentView.as_view(), name="offer-verify-payment"),
    path("orders/<int:order_id>/handover-code/", HandoverCodeView.as_view(), name="order-handover-code"),
    path("orders/<int:order_id>/confirm-handover/", ConfirmHandoverView.as_view(), name="order-confirm-handover"),
]
