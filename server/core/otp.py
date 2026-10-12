"""Rate limits for sign in attempts, kept in the database."""

import datetime
import ipaddress
import math

from django.http import HttpRequest
from django.utils import timezone

from server.core.models import OTPAttempt
from server.duplicates.identity import normalize_email

MINUTE = datetime.timedelta(minutes=1)
HOUR = datetime.timedelta(hours=1)

# (fields counted together, most allowed, window). HOUR is the longest window:
# rows older are pruned. The tight limit is per (email, IP); the looser one
# per email is all a stranger elsewhere can use up of an owner's attempts.
LIMITS = {
    OTPAttempt.Kind.SEND: [
        (("email", "ip"), 3, 10 * MINUTE),
        (("email",), 10, HOUR),
        (("ip",), 20, HOUR),
    ],
    OTPAttempt.Kind.GUESS: [
        (("email", "ip"), 5, 10 * MINUTE),
        (("email",), 30, HOUR),
        (("ip",), 50, HOUR),
    ],
    # Failed passwords only: a success is withdrawn. The "email" is the username.
    OTPAttempt.Kind.PASSWORD: [
        (("email", "ip"), 10, 10 * MINUTE),
        (("email",), 50, HOUR),
    ],
}


def client_ip(request: HttpRequest) -> str:
    """The caller's IP, or for IPv6 its /64, since one host can hold a whole
    /64. Fly's proxy sets Fly-Client-IP, replacing any the client sent. Nginx
    is the only other hop, so REMOTE_ADDR is only useful off Fly (tests,
    local). X-Forwarded-For's first hop is whatever the client wrote."""
    raw = request.META.get("HTTP_FLY_CLIENT_IP") or request.META.get("REMOTE_ADDR") or ""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return raw[:64]
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def attempt(kind: OTPAttempt.Kind, email: str, ip: str) -> int:
    """Record an attempt of `kind`, then count it with the others in each
    window. Over a limit, it is withdrawn and this returns the minutes until
    another is allowed; 0 means go ahead.

    Inserting before counting makes this race free without locks: of any
    concurrent attempts let through, the last to insert counted all of them,
    so no more than the limit get through. The email is normalized, so Gmail
    dot variants, which all sign in to one account, share its limits.
    """
    current = timezone.now()
    OTPAttempt.objects.filter(created_at__lt=current - HOUR).delete()
    values = {"email": normalize_email(email)[:254], "ip": ip}
    row = OTPAttempt.objects.create(kind=kind, **values)
    windows = [
        (
            OTPAttempt.objects.filter(
                kind=kind, created_at__gt=current - window, **{f: values[f] for f in fields}
            ),
            limit,
            window,
        )
        for fields, limit, window in LIMITS[kind]
    ]
    full = [(recent, limit, window) for recent, limit, window in windows if recent.count() > limit]
    if not full:
        return 0
    row.delete()
    wait = datetime.timedelta(0)
    for recent, limit, window in full:
        times = list(recent.order_by("-created_at").values_list("created_at", flat=True)[:limit])
        # Full while the limit-th newest is in the window, until it ages out.
        if len(times) == limit:
            wait = max(wait, times[-1] + window - current)
    return max(1, math.ceil(wait / MINUTE))


def withdraw(kind: OTPAttempt.Kind, email: str, ip: str) -> None:
    """Uncount one attempt, as `attempt` recorded it."""
    rows = OTPAttempt.objects.filter(kind=kind, email=normalize_email(email)[:254], ip=ip)
    OTPAttempt.objects.filter(id__in=rows.order_by("-id").values("id")[:1]).delete()


def too_many(minutes: int) -> dict[str, str]:
    unit = "minute" if minutes == 1 else "minutes"
    return {"message": f"Too many attempts. Try again in {minutes} {unit}."}
