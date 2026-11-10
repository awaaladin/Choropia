from django.urls import path

from .views import CancelOfferView, ConversationOffersView, DeclineOfferView, OfferCheckoutView, OfferDetailView

urlpatterns = [
    path("conversations/<int:conversation_id>/offers/", ConversationOffersView.as_view(), name="conversation-offers"),
    path("offers/<uuid:offer_id>/", OfferDetailView.as_view(), name="offer-detail"),
    path("offers/<uuid:offer_id>/cancel/", CancelOfferView.as_view(), name="offer-cancel"),
    path("offers/<uuid:offer_id>/decline/", DeclineOfferView.as_view(), name="offer-decline"),
    path("offers/<uuid:offer_id>/checkout/", OfferCheckoutView.as_view(), name="offer-checkout"),
]
