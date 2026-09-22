from django.views.generic import TemplateView


class FeedView(TemplateView):
    template_name = "core/feed.html"


class LoginView(TemplateView):
    template_name = "core/login.html"


class RegisterView(TemplateView):
    template_name = "core/register.html"


class ForgotPasswordView(TemplateView):
    template_name = "core/forgot_password.html"


class ResetPasswordView(TemplateView):
    template_name = "core/reset_password.html"


class ListingDetailView(TemplateView):
    template_name = "core/listing_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["listing_id"] = kwargs["listing_id"]
        return context


class ConversationsView(TemplateView):
    template_name = "core/conversations.html"


class ChatView(TemplateView):
    template_name = "core/chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["conversation_id"] = kwargs["conversation_id"]
        return context


class OrdersView(TemplateView):
    template_name = "core/orders.html"


class OrderDetailView(TemplateView):
    template_name = "core/order_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order_id"] = kwargs["order_id"]
        return context


class ProfileView(TemplateView):
    template_name = "core/profile.html"


class MarketplaceView(TemplateView):
    template_name = "core/marketplace.html"


class CreateListingView(TemplateView):
    template_name = "core/create_listing.html"


class NotificationsView(TemplateView):
    template_name = "core/notifications.html"


class MerchantProfileView(TemplateView):
    template_name = "core/merchant_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["merchant_id"] = kwargs["merchant_id"]
        return context


class ApplyMerchantView(TemplateView):
    template_name = "core/apply_merchant.html"
