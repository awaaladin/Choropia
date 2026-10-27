from django.urls import path

from . import views

urlpatterns = [
    path("dispatch/areas/", views.AreasView.as_view()),
    path("dispatch/driver/me/", views.DriverMeView.as_view()),
    path("dispatch/driver/documents/", views.DriverDocumentsView.as_view()),
    path("dispatch/driver/routes/", views.DriverRoutesView.as_view()),
    path("dispatch/driver/routes/<int:pk>/", views.DriverRouteDetailView.as_view()),
    path("dispatch/driver/jobs/", views.DriverJobsView.as_view()),
    path("dispatch/driver/jobs/<int:pk>/accept/", views.JobActionView.as_view(action="accept")),
    path("dispatch/driver/jobs/<int:pk>/decline/", views.JobActionView.as_view(action="decline")),
    path("dispatch/driver/jobs/<int:pk>/pickup/", views.JobActionView.as_view(action="pickup")),
    path("dispatch/driver/jobs/<int:pk>/deliver/", views.JobDeliverView.as_view()),
    path("dispatch/drivers/", views.DriversBrowseView.as_view()),
    path("dispatch/listings/<int:listing_id>/delivery/", views.ListingDeliveryView.as_view()),
    path("dispatch/orders/<int:pk>/delivery/", views.OrderDeliveryView.as_view()),
    path("dispatch/orders/<int:pk>/delivery/reassign/", views.OrderReassignView.as_view()),
    path("dispatch/orders/<int:pk>/delivery/proof/", views.OrderProofView.as_view()),
]
