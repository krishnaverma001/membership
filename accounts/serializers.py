# accounts/serializers.py

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from .models import Education, WorkExperience, Skill, ShareableLink, ProfileView
import os
from django.core.files.storage import default_storage

User = get_user_model()


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'institution', 'degree', 'field_of_study', 'start_date',
                  'end_date', 'is_current', 'description']
        read_only_fields = ['id']


class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExperience
        fields = ['id', 'company', 'position', 'start_date', 'end_date',
                  'is_current', 'description']
        read_only_fields = ['id']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'proficiency']
        read_only_fields = ['id']


# class LanguageSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Language
#         fields = ['id', 'name', 'proficiency']
#         read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'password',
                  'password_confirm', 'profile_photo', 'resume']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def validate_resume(self, value):
        if value:
            ext = value.name.split('.')[-1].lower()
            if ext not in ['pdf', 'doc', 'docx']:
                raise serializers.ValidationError("Only PDF and DOC files are allowed.")

            if value.size > 5 * 1024 * 1024:  # 5 MB limit
                raise serializers.ValidationError("Resume file size should not exceed 5MB.")

        return value

    def validate_profile_photo(self, value):
        if value:
            if value.size > 2 * 1024 * 1024:  # 2 MB limit
                raise serializers.ValidationError("Profile photo size should not exceed 2MB.")
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        profile_photo = validated_data.pop('profile_photo', None)
        resume = validated_data.pop('resume', None)

        user = User.objects.create_user(**validated_data)
        user.set_password(password)

        def rename_file(file_obj, folder):
            if not file_obj:
                return None

            ext = os.path.splitext(file_obj.name)[1]
            new_filename = f"{user.membership_id}{ext}"
            new_path = os.path.join(folder, new_filename)
            saved_path = default_storage.save(new_path, file_obj)

            return saved_path

        if profile_photo:
            user.profile_photo.name = rename_file(profile_photo, "profiles")

        if resume:
            user.resume.name = rename_file(resume, "resumes")

        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    education_set = EducationSerializer(many=True, read_only=True)
    work_experience_set = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    # languages = LanguageSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'membership_id', 'username', 'email', 'first_name',
                  'last_name', 'full_name', 'phone', 'gender', 'dob', 'profile_photo', 'resume',
                  'status', 'is_verified', 'is_blocked', 'created_at', 'updated_at',
                  'education_set', 'work_experience_set', 'skills']
        read_only_fields = ['id', 'membership_id', 'username', 'email', 'is_verified',
                            'is_blocked', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserUpdateSerializer(serializers.ModelSerializer):
    education_set = EducationSerializer(many=True, read_only=True)
    work_experience_set = WorkExperienceSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'gender', 'dob', 'profile_photo', 'resume', 'education_set', 'work_experience_set',]

    def validate_resume(self, value):
        if value:
            ext = value.name.split('.')[-1].lower()
            if ext not in ['pdf', 'doc', 'docx']:
                raise serializers.ValidationError("Only PDF and DOC files are allowed.")
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Resume file size should not exceed 5MB.")
        return value

    def validate_profile_photo(self, value):
        if value:
            if value.size > 2 * 1024 * 1024:
                raise serializers.ValidationError("Profile photo size should not exceed 2MB.")
        return value

class ShareableLinkSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()
    is_valid = serializers.ReadOnlyField()
    view_count = serializers.SerializerMethodField()

    class Meta:
        model = ShareableLink
        fields = ['id', 'token', 'expiry_days', 'created_at', 'expires_at',
                  'is_active', 'is_valid', 'share_url', 'view_count']
        read_only_fields = ['id', 'token', 'created_at', 'expires_at', 'is_active']

    def get_share_url(self, obj):
        request = self.context.get('request')
        if request:
            domain = request.get_host()
            scheme = 'https' if request.is_secure() else 'http'
            return f"{scheme}://{domain}/profile/view/{obj.token}"

        return f"/profile/view/{obj.token}"

    def get_view_count(self, obj):
        return obj.views.count()


class ProfileViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileView
        fields = ['id', 'viewer_ip', 'viewer_user_agent', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']


class PublicProfileSerializer(serializers.ModelSerializer):
    """Serializer for public profile view via shareable link"""
    education_set = EducationSerializer(many=True, read_only=True)
    work_experience_set = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    # languages = LanguageSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['full_name', 'created_at', 'profile_photo', 'resume', 'education_set',
                  'work_experience_set', 'skills']

    def get_full_name(self, obj):
        return obj.get_full_name()


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin serializer with full control"""
    education_set = EducationSerializer(many=True, read_only=True)
    work_experience_set = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    # languages = LanguageSerializer(many=True, read_only=True)
    status = serializers.ReadOnlyField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'membership_id', 'username', 'email', 'first_name',
                  'last_name', 'full_name', 'phone', 'profile_photo', 'resume',
                  'status', 'is_verified', 'is_blocked', 'is_active', 'is_staff',
                  'created_at', 'updated_at', 'education_set', 'work_experience_set',
                  'skills']
        read_only_fields = ['id', 'membership_id', 'username', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.get_full_name()
