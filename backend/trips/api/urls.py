from django.urls import path

from . import views

urlpatterns = [
    path("trips/plan", views.plan),
    path("trips/heatmap", views.heatmap),
    path("places", views.places),
]
