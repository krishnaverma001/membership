from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import User

@receiver(post_delete, sender=User)
def auto_delete_user_files_on_delete(sender, instance, **kwargs):
    if instance.profile_photo:
        instance.profile_photo.delete(save=False)
    if instance.resume:
        instance.resume.delete(save=False)
