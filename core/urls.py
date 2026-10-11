from django.urls import re_path

from . import views

# Matches every path not already claimed by api/v1/, api/schema/, api/docs/, or admin/ (those
# are registered first in config/urls.py and win). Anything else is a React Router route —
# serve the SPA shell and let the client-side router take over.
urlpatterns = [
    re_path(r"^.*$", views.SPAView.as_view(), name="spa"),
]
