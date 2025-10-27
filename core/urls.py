# core/urls.py

from django.urls import path
from .views import LoginPageView, DashboardPageView, RegisterPageView, IndexPageView, EditProfilePageView, ShareableProfileView
from django.views.generic import TemplateView

urlpatterns = [
    path('', IndexPageView.as_view(), name="index"),
    path('login/', LoginPageView.as_view(), name="login"),
    path('register/', RegisterPageView.as_view(), name="register"),
    path('dashboard/', DashboardPageView.as_view(), name="dashboard"),
    path('edit-profile/', EditProfilePageView.as_view(), name="edit-profile"),
    path('profile/view/<uuid:token>', ShareableProfileView.as_view(), name="shareable-profile"),

    path('link-expired/', TemplateView.as_view(template_name='link_expired.html'), name='link-expired'),
    path('link-not-found/', TemplateView.as_view(template_name='link_not_found.html'), name='link-not-found'),
]
