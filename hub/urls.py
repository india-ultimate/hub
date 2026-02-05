"""
URL configuration for hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

from server.admin_views import csv_imports_view

_admin_urls = admin.site.get_urls()


def _admin_get_urls() -> list[URLPattern | URLResolver]:
    return [
        path("csv-imports/", admin.site.admin_view(csv_imports_view), name="csv_imports"),
        *_admin_urls,
    ]


admin.site.get_urls = _admin_get_urls  # type: ignore[method-assign]

urlpatterns = [
    path("", include("server.urls")),
    path("", include("django_prometheus.urls")),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("admin/", admin.site.urls),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
