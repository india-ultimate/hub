"""Old /media/<name> links, from before files moved to Cloudinary."""

from django.http import Http404, HttpRequest, HttpResponsePermanentRedirect

from server.storage import kinds

ARCHIVED = ("vaccination_certificates/",)


def old_media_link(request: HttpRequest, name: str) -> HttpResponsePermanentRedirect:
    if not name or ".." in name.split("/") or name.startswith(ARCHIVED):
        raise Http404
    return HttpResponsePermanentRedirect(kinds.url(name))
