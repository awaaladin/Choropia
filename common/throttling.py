from rest_framework.permissions import SAFE_METHODS


class ScopedWritesMixin:
    """Applies a stricter throttle scope to writes only (sending, posting, ordering), so reading and polling stay fast."""

    write_throttle_scope = None

    def get_throttles(self):
        if self.write_throttle_scope and self.request.method not in SAFE_METHODS:
            self.throttle_scope = self.write_throttle_scope
        return super().get_throttles()
