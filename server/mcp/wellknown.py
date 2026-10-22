from django.conf import settings
from django.http import HttpRequest
from oauth2_provider.views import OAuthProtectedResourceMetadataView


class ProtectedResourceMetadataView(OAuthProtectedResourceMetadataView):
    def get_resource(self, request: HttpRequest) -> str:
        return str(settings.MCP_RESOURCE_URL)

    def get_authorization_servers(self, request: HttpRequest) -> list[str]:
        return [settings.PUBLIC_URL]

    def get_resource_name(self) -> str:
        return "India Ultimate Hub"
