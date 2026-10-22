from django.urls import URLPattern, URLResolver, include, path
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider import views as oauth

from server.mcp import redirects, upload, views
from server.mcp.views import enabled_only
from server.mcp.wellknown import ProtectedResourceMetadataView

# DOT reverses these names in the oauth2_provider namespace.
oauth_patterns = [
    path("o/authorize/", enabled_only(views.ConsentView.as_view()), name="authorize"),
    path("o/token/", enabled_only(oauth.TokenView.as_view()), name="token"),
    path("o/revoke_token/", enabled_only(oauth.RevokeTokenView.as_view()), name="revoke-token"),
    path(
        "o/register/",
        enabled_only(redirects.RegistrationView.as_view()),
        name="dcr-register",
    ),
    path(
        "o/register/<str:client_id>/",
        enabled_only(redirects.RegistrationManagementView.as_view()),
        name="dcr-register-management",
    ),
    path(
        ".well-known/oauth-authorization-server",
        enabled_only(oauth.OAuthServerMetadataView.as_view()),
        name="oauth-server-metadata",
    ),
]

protected_resource = enabled_only(ProtectedResourceMetadataView.as_view())

urlpatterns: list[URLPattern | URLResolver] = [
    path("", include((oauth_patterns, "oauth2_provider"))),
    path(".well-known/oauth-protected-resource", protected_resource),
    path(".well-known/oauth-protected-resource/mcp", protected_resource),
    path("mcp", views.mcp, name="mcp"),
    path(
        "mcp/upload/<str:token>",
        enabled_only(csrf_exempt(upload.upload)),
        name="mcp-upload",
    ),
]
