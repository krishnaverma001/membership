from django.views.generic import TemplateView
from django.shortcuts import redirect, render

from accounts.models import ShareableLink


class LoginPageView(TemplateView):
    template_name = "login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)

class DashboardPageView(TemplateView):
    template_name = "dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if getattr(request.user, 'initial_onboarding', True):
            return redirect('edit-profile')

        return super().dispatch(request, *args, **kwargs)

class EditProfilePageView(TemplateView):
    template_name = "edit_profile.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        self.is_onboarding = getattr(request.user, 'initial_onboarding', True)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_onboarding'] = self.is_onboarding
        return context

class RegisterPageView(TemplateView):
    template_name = "register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)

class IndexPageView(TemplateView):
    template_name = "index.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')

        return super().dispatch(request, *args, **kwargs)

class ShareableProfileView(TemplateView):
    template_name = "public_profile.html"

    def get(self, request, token, *args, **kwargs):
        link = ShareableLink.objects.filter(token=token).first()

        if not link:
            return redirect("link-not-found")

        if not link.is_valid:
            return redirect("link-expired")

        return render(request, self.template_name, {"token": token})