from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [
    path("admin/", admin.site.urls),

    # logins
    path("login/", include(("apps.login.urls", "login"), namespace="login")),

    # apps urls
    path("admins/", include(("apps.admins.urls", "admins"), namespace="admins")),
    path("members/", include(("apps.jobs.member_urls", "member-jobs"), namespace="member-jobs")),
    path("members/", include(("apps.members.urls", "members"), namespace="members")),
    path("jobs/", include(("apps.jobs.urls", "jobs"), namespace="jobs")),

    # swagger urls
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api-docs/", SpectacularSwaggerView.as_view(template_name="swagger-ui.html", url_name="schema"), name="swagger-ui"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
