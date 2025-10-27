# accounts/views.py

from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from django.views import View
from django.http import FileResponse, Http404
from .models import Education, WorkExperience, Skill, ShareableLink, ProfileView
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, UserUpdateSerializer,
    EducationSerializer, WorkExperienceSerializer, SkillSerializer,
    ShareableLinkSerializer, ProfileViewSerializer, PublicProfileSerializer, AdminUserSerializer
)
from .tasks import send_verification_email, expire_shareable_links
from urllib.parse import unquote
from django.conf import settings
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.shortcuts import render
import os
import mimetypes

User = get_user_model()


class CookieLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        try:
            user_in_db = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=400)

        user = authenticate(request, email=email, password=password)

        if user_in_db.status == 'blocked':
            return Response({"message": "This account is blocked"}, status=403)

        if not user.is_verified:
            return Response({"message": "Please verify your email first."}, status=403)

        if not user:
            return Response({"message": "Invalid credentials"}, status=400)

        if request.user.is_authenticated:
            return Response({"message": "Already logged in."}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = Response({
            "message": "Login successful",
            "user": {"email": user.email, "membership_id": str(user.membership_id)},
        }, status=status.HTTP_200_OK)

        # Secure cookie setup
        cookie_settings = {
            "httponly": True,
            "secure": not settings.DEBUG,  # True
            "samesite": "Lax",
        }

        response.set_cookie("access_token", access_token, max_age=3600, **cookie_settings)
        response.set_cookie("refresh_token", str(refresh), max_age=7 * 24 * 3600, **cookie_settings)

        return response


class CookieLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if not refresh_token:
                return Response({"message": "No refresh token found"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            response = Response({"message": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            send_verification_email.delay(user.id)

            return Response({
                'message': 'Registration successful. Please check your email to verify your account.',
                'email': user.email
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(View):
    def get(self, request, token):
        signer = TimestampSigner()
        try:
            token = unquote(token)
            user_id = signer.unsign(token, max_age=3600)  # 1 hours
            user = User.objects.get(id=user_id)

            if not user.is_verified:
                user.is_verified = True
                user.is_active = True
                user.save()

            return render(request, "verification_success.html", {"membership_id": user.membership_id})

        except SignatureExpired:
            return render(request, "verification_failed.html",
                          {"message": "Verification link has expired. Please register again."})
        except (BadSignature, User.DoesNotExist):
            return render(request, "verification_failed.html", {"message": "Invalid verification link."})


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        if data.get('profile_photo'):
            data['profile_photo'] = request.build_absolute_uri(data['profile_photo'])
        if data.get('resume'):
            data['resume'] = request.build_absolute_uri(data['resume'])

        return Response(data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        mutable_data = request.data.copy()

        edu_count = int(mutable_data.get('education_count', 0))
        exp_count = int(mutable_data.get('experience_count', 0))

        profile_photo = request.FILES.get('profile_photo')
        resume = request.FILES.get('resume')

        education = []
        experience = []

        for i in range(edu_count):
            education.append({
                'institution': mutable_data.get(f'institution_{i}'),
                'degree': mutable_data.get(f'degree_{i}'),
                'field_of_study': mutable_data.get(f'field_of_study_{i}'),
                'start_date': mutable_data.get(f'edu_start_date_{i}'),
                'end_date': mutable_data.get(f'edu_end_date_{i}') or None,
                'is_current': mutable_data.get(f'edu_is_current_{i}') == 'on',
                'description': mutable_data.get(f'edu_description_{i}'),
            })

        for i in range(exp_count):
            experience.append({
                'company': mutable_data.get(f'company_{i}'),
                'position': mutable_data.get(f'position_{i}'),
                'start_date': mutable_data.get(f'exp_start_date_{i}'),
                'end_date': mutable_data.get(f'exp_end_date_{i}') or None,
                'is_current': mutable_data.get(f'exp_is_current_{i}') == 'on',
                'description': mutable_data.get(f'exp_description_{i}', ''),
            })

        serializer = self.get_serializer(instance, data=mutable_data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if profile_photo:
            instance.profile_photo = profile_photo
        if resume:
            instance.resume = resume

        self.perform_update(serializer)

        # Recreate related models
        instance.education_set.all().delete()
        instance.work_experience_set.all().delete()

        for edu in education:
            if edu['institution']:
                Education.objects.create(user=instance, **edu)
        for exp in experience:
            if exp['company']:
                WorkExperience.objects.create(user=instance, **exp)

        if getattr(instance, 'initial_onboarding', None) is not None and instance.initial_onboarding:
            instance.initial_onboarding = False
            instance.save(update_fields=['initial_onboarding'])

        response_data = self.get_serializer(instance).data

        if response_data.get('profile_photo'):
            response_data['profile_photo'] = request.build_absolute_uri(response_data['profile_photo'])
        if response_data.get('resume'):
            response_data['resume'] = request.build_absolute_uri(response_data['resume'])

        return Response({
            "message": "Profile updated successfully",
            "user": response_data
        }, status=status.HTTP_200_OK)

@method_decorator(xframe_options_sameorigin, name="dispatch")
class ResumePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, membership_id):
        try:
            user = User.objects.get(membership_id=membership_id)
            if not user.resume:
                raise Http404("No resume found")

            file_path = user.resume.path
            if not os.path.exists(file_path):
                raise Http404("File not found")

            mime_type, _ = mimetypes.guess_type(file_path)
            response = FileResponse(open(file_path, 'rb'), content_type=mime_type or 'application/octet-stream')
            response["Content-Disposition"] = f'inline; filename="{os.path.basename(file_path)}"'
            return response

        except User.DoesNotExist:
            raise Http404("User not found")

class EducationViewSet(viewsets.ModelViewSet):
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Education.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorkExperienceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkExperienceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WorkExperience.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SkillViewSet(viewsets.ModelViewSet):
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Skill.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# class LanguageViewSet(viewsets.ModelViewSet):
#     """CRUD operations for languages"""
#     serializer_class = LanguageSerializer
#     permission_classes = [IsAuthenticated]
#
#     def get_queryset(self):
#         return Language.objects.filter(user=self.request.user)
#
#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)

class ShareableLinkViewSet(viewsets.ModelViewSet):
    serializer_class = ShareableLinkSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return ShareableLink.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        expiry_days = int(request.data.get('expiry_days', 7))

        link = ShareableLink.objects.create(
            user=request.user,
            expiry_days=expiry_days
        )

        serializer = self.get_serializer(link)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def views(self, request, pk=None):
        """Get all views for a specific link"""
        link = self.get_object()
        views = link.views.all()
        serializer = ProfileViewSerializer(views, many=True)
        return Response({
            'total_views': views.count(),
            'views': serializer.data
        })


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def public_profile_view(request, token):
    try:
        link = get_object_or_404(ShareableLink, token=token)
    except ShareableLink.DoesNotExist:
        return Response({'error': 'This link does not exist or has been deleted.'}, status=404)

    if not link.is_active:
        return Response({'error': 'This link has been deleted or deactivated.'}, status=404)

    if not link.is_valid:
        return Response({'error': 'This link has expired or is no longer active.'}, status=410)

    if request.method == 'POST':
        viewer_ip = request.META.get('REMOTE_ADDR')
        viewer_user_agent = request.META.get('HTTP_USER_AGENT', '')

        ProfileView.objects.create(
            shareable_link=link,
            viewer_ip=viewer_ip,
            viewer_user_agent=viewer_user_agent
        )

        return Response({'message': 'View logged successfully'})

    # GET request - return profile data
    serializer = PublicProfileSerializer(link.user)
    return Response(serializer.data)

class PublicResumePreviewView(APIView):
    permission_classes = []

    def get(self, request, token):
        try:
            link = ShareableLink.objects.get(token=token)
        except ShareableLink.DoesNotExist:
            raise Http404("Link not found")

        if not link.is_active or not link.is_valid:
            raise Http404("Link expired or deactivated")

        user = link.user
        if not user.resume or not os.path.exists(user.resume.path):
            raise Http404("Resume not found")

        mime_type, _ = mimetypes.guess_type(user.resume.path)
        response = FileResponse(
            open(user.resume.path, 'rb'),
            content_type=mime_type or 'application/octet-stream'
        )
        response["Content-Disposition"] = f'inline; filename="{os.path.basename(user.resume.name)}"'
        return response

# Admin Views
class AdminDashboardView(generics.GenericAPIView):
    """Admin dashboard with statistics"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.filter(is_staff=False).count()
        active_users = User.objects.filter(is_verified=True, is_blocked=False, is_staff=False).count()
        pending_users = User.objects.filter(is_verified=False, is_staff=False).count()
        blocked_users = User.objects.filter(is_blocked=True, is_staff=False).count()

        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'pending_users': pending_users,
            'blocked_users': blocked_users
        })


class AdminUserViewSet(viewsets.ModelViewSet):
    """Admin user management"""
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.filter(is_staff=False)

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status', None)
        search = self.request.query_params.get('search', None)

        if status_filter:
            if status_filter == 'active':
                queryset = queryset.filter(is_verified=True, is_blocked=False)
            elif status_filter == 'pending':
                queryset = queryset.filter(is_verified=False)
            elif status_filter == 'blocked':
                queryset = queryset.filter(is_blocked=True)

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(membership_id__icontains=search)
            )

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block a user"""
        user = self.get_object()
        user.is_blocked = True
        user.is_active = False
        user.save()
        return Response({'message': f'User {user.get_full_name()} has been blocked.'})

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock a user"""
        user = self.get_object()
        user.is_blocked = False
        if user.is_verified:
            user.is_active = True
        user.save()
        return Response({'message': f'User {user.get_full_name()} has been unblocked.'})

    @action(detail=True, methods=['get'])
    def profile_views(self, request, pk=None):
        """Get profile view statistics for a user"""
        user = self.get_object()
        links = user.shareable_links.all()
        total_views = ProfileView.objects.filter(shareable_link__in=links).count()

        return Response({
            'total_links': links.count(),
            'total_views': total_views,
            'active_links': links.filter(is_active=True, expires_at__gt=timezone.now()).count()
        })
