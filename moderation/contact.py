from django.conf import settings
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.net import client_ip

from .models import ContactMessage


class ContactSerializer(serializers.ModelSerializer):
    # A hidden field real people never fill in; bots do. Anything in it is quietly dropped.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "topic", "message", "website")

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Tell us a little more (at least 10 characters).")
        return value


class ContactView(APIView):
    """POST /contact/: anyone (signed in or not) can write to us. Staff are emailed straight away."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "contact"

    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get("website"):
            return Response({"detail": "Thanks, we got your message."}, status=201)  # a bot: pretend it worked
        user = _signed_in_user(request)
        message = ContactMessage.objects.create(
            name=data["name"].strip()[:120],
            email=data["email"],
            topic=data["topic"],
            message=data["message"],
            user=user,
            ip_address=client_ip(request),
        )
        _notify(message)
        return Response({"detail": "Thanks, we got your message and will reply by email."}, status=201)


def _signed_in_user(request):
    from rest_framework_simplejwt.authentication import JWTAuthentication

    try:
        result = JWTAuthentication().authenticate(request)
    except Exception:  # noqa: BLE001 - a bad token just means "not signed in" here
        return None
    return result[0] if result else None


def _notify(message):
    from notifications import emails, staff_alerts

    topic = message.get_topic_display()
    staff_alerts.alert(
        f"{topic}: message from {message.name}",
        "A message came in through the Contact page",
        [f"From: {message.name} <{message.email}>" + (f" (signed in as user {message.user_id})" if message.user_id else ""), f"Topic: {topic}", message.message],
        "/staff/inbox/",
    )
    emails.send_email_after_commit(
        message.email,
        "We got your message | Choropia",
        "contact_received",
        {"name": message.name.split(" ")[0] or "there", "message": message.message},
    )
