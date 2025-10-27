# accounts/models.py

import uuid
import os
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.files.storage import default_storage

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

def profile_photo_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"profiles/{instance.membership_id}{ext}"

def resume_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"resumes/{instance.membership_id}{ext}"

class User(AbstractUser):
    membership_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        blank=True, null=True
    )
    dob = models.DateField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to=profile_photo_path, blank=True, null=True)
    resume = models.FileField(upload_to=resume_path, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    initial_onboarding = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} - ({self.membership_id})"

    @property
    def status(self):
        if self.is_blocked:
            return 'blocked'
        elif self.is_verified:
            return 'active'
        else:
            return 'pending'

    def save(self, *args, **kwargs):
        try:
            old = User.objects.get(pk=self.pk)
        except User.DoesNotExist:
            old = None

        # Delete old profile photo if new one uploaded
        if old and self.profile_photo and old.profile_photo != self.profile_photo:
            if default_storage.exists(old.profile_photo.name):
                default_storage.delete(old.profile_photo.name)

        # Delete old resume if new one uploaded
        if old and self.resume and old.resume != self.resume:
            if default_storage.exists(old.resume.name):
                default_storage.delete(old.resume.name)

        super().save(*args, **kwargs)

class Education(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='education_set')
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.degree} at {self.institution}"


class WorkExperience(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_experience_set')
    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.position} at {self.company}"


class Skill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    proficiency = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert')
        ],
        default='intermediate'
    )

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.name} - {self.proficiency}"


# class Language(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='languages')
#     name = models.CharField(max_length=100)
#     proficiency = models.CharField(
#         max_length=20,
#         choices=[
#             ('basic', 'Basic'),
#             ('conversational', 'Conversational'),
#             ('fluent', 'Fluent'),
#             ('native', 'Native')
#         ],
#         default='conversational'
#     )
#
#     class Meta:
#         unique_together = ['user', 'name']
#
#     def __str__(self):
#         return f"{self.name} - {self.proficiency}"


class ShareableLink(models.Model):
    EXPIRY_CHOICES = [
        (1, '1 Day'),
        (2, '2 Days'),
        (7, '7 Days'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shareable_links')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expiry_days = models.IntegerField(choices=EXPIRY_CHOICES, default=7)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=self.expiry_days)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return self.is_active and timezone.now() < self.expires_at

    def __str__(self):
        return f"Link for {self.user.get_full_name()} - Expires: {self.expires_at}"

    class Meta:
        ordering = ['-created_at']


class ProfileView(models.Model):
    shareable_link = models.ForeignKey(ShareableLink, on_delete=models.CASCADE, related_name='views')
    viewer_ip = models.GenericIPAddressField()
    viewer_user_agent = models.TextField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"View of {self.shareable_link.user.get_full_name()} at {self.viewed_at}"