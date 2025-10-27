# accounts/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from urllib.parse import quote


User = get_user_model()

@shared_task
def send_verification_email(user_id):
    user = User.objects.get(id=user_id)

    signer = TimestampSigner()
    token = signer.sign(user_id)

    print(token, quote(token))

    verification_url = f"http://localhost:8000/api/verify-email/{quote(token)}/"

    context = {
        'name': user.get_full_name(),
        'membership_id': user.membership_id,
        'verification_url': verification_url,
        'year': timezone.now().year,
    }

    html_content = render_to_string('email_verification.html', context)

    subject = 'Verify Your Email - Membership Portal'

    send_mail(
        subject=subject,
        message='Sorry, we are facing some errors at the moment. Please try again after some time.',
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_content,
        fail_silently=False,
    )

    return f"Verification email sent to {user.email}"


@shared_task
def expire_shareable_links():
    from .models import ShareableLink

    expired_links = ShareableLink.objects.filter(
        is_active=True,
        expires_at__lt=timezone.now()           # Passed expiry date
    )

    count = expired_links.count()
    expired_links.update(is_active=False)

    return f"Expired {count} shareable links"


@shared_task
def send_profile_view_notification(user_id, viewer_count):
    """Send notification to user when their profile is viewed"""
    try:
        user = User.objects.get(id=user_id)

        subject = 'Your Profile Was Viewed - Membership Portal'
        message = f"""
        Hello {user.get_full_name()},

        Your profile has been viewed {viewer_count} time(s) via a shareable link.

        You can check the details of who viewed your profile in your dashboard.

        Best regards,
        Membership Portal Team
        """

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=True,
        )

        return f"Notification sent to {user.email}"
    except User.DoesNotExist:
        return f"User with id {user_id} not found"
    except Exception as e:
        return f"Error sending notification: {str(e)}"