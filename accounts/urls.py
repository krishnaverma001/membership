# accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserRegistrationView, UserProfileView,
    EducationViewSet, WorkExperienceViewSet, SkillViewSet,
    ShareableLinkViewSet, public_profile_view,
    AdminDashboardView, AdminUserViewSet,
    CookieLoginView, CookieLogoutView,
    VerifyEmailView, ResumePreviewView, PublicResumePreviewView
)

router = DefaultRouter()
router.register(r'education', EducationViewSet, basename='education')
router.register(r'work-experience', WorkExperienceViewSet, basename='work-experience')

# router.register(r'skills', SkillViewSet, basename='skills')
# router.register(r'languages', LanguageViewSet, basename='languages')

router.register(r'shareable-links', ShareableLinkViewSet, basename='shareable-links')

# router.register(r'admin/users', AdminUserViewSet, basename='admin-users')

urlpatterns = [
    path("login/", CookieLoginView.as_view(), name="cookie_login"),
    path("logout/", CookieLogoutView.as_view(), name="cookie_logout"),
    path('register/', UserRegistrationView.as_view(), name='register'),

    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),

    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('resume/preview/<uuid:membership_id>/', ResumePreviewView.as_view(), name='preview_resume'),

    path('profile/view/<uuid:token>/', public_profile_view, name='public-profile-view'),
    path('resume/public/<uuid:token>/', PublicResumePreviewView.as_view(), name='public-resume'),

    # Admin
    # path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),


    # Router URLs
    path('', include(router.urls)),
]