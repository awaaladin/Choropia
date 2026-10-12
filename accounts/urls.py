from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .google import GoogleLoginView
from .two_factor import (
    TwoFactorConfirmView,
    TwoFactorDisableView,
    TwoFactorSetupView,
    TwoFactorStatusView,
    TwoFactorVerifyView,
)
from .views import (
    LoginView,
    LogoutAllView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/logout-all/", LogoutAllView.as_view(), name="logout_all"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("auth/google/", GoogleLoginView.as_view(), name="google_login"),
    path("auth/2fa/status/", TwoFactorStatusView.as_view(), name="2fa_status"),
    path("auth/2fa/setup/", TwoFactorSetupView.as_view(), name="2fa_setup"),
    path("auth/2fa/confirm/", TwoFactorConfirmView.as_view(), name="2fa_confirm"),
    path("auth/2fa/disable/", TwoFactorDisableView.as_view(), name="2fa_disable"),
    path("auth/2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa_verify"),
    path("users/me/", MeView.as_view(), name="me"),
] + router.urls
