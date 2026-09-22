from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from common.models import TimeStampedModel

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_moderator = models.BooleanField(
        default=False, help_text="Can review flagged listings/users and merchant applications."
    )

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [models.Index(fields=["phone_number"])]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        return self.first_name or self.email


class Profile(TimeStampedModel):
    class Theme(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.CharField(max_length=300, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    location = models.CharField(
        max_length=150,
        blank=True,
        help_text="Free-text area/campus within the pilot city, e.g. 'Uyo - Use of Ibom Campus'.",
    )
    theme_preference = models.CharField(
        max_length=10, choices=Theme.choices, default=Theme.LIGHT
    )

    def __str__(self):
        return f"Profile<{self.user.email}>"
