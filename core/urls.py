from django.urls import path

from . import views

urlpatterns = [
    path("", views.FeedView.as_view(), name="feed"),
    path("marketplace/", views.MarketplaceView.as_view(), name="marketplace"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset-password"),
    path("listings/create/", views.CreateListingView.as_view(), name="create-listing"),
    path("listings/<int:listing_id>/", views.ListingDetailView.as_view(), name="listing-detail"),
    path("messages/", views.ConversationsView.as_view(), name="conversations"),
    path("messages/<int:conversation_id>/", views.ChatView.as_view(), name="chat"),
    path("orders/", views.OrdersView.as_view(), name="orders"),
    path("orders/<int:order_id>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("notifications/", views.NotificationsView.as_view(), name="notifications"),
    path("merchants/apply/", views.ApplyMerchantView.as_view(), name="apply-merchant"),
    path("merchants/<int:merchant_id>/", views.MerchantProfileView.as_view(), name="merchant-profile"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
]
