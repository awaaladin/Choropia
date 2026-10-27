from django.urls import path

from . import views

urlpatterns = [
    path("legal/", views.LegalIndexView.as_view()),
    path("legal/accept/", views.AcceptanceView.as_view()),
    path("legal/<slug:slug>/", views.LegalDocumentView.as_view()),
]
