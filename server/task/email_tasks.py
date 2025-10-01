from typing import Any

from django.core import mail
from django.core.mail import EmailMultiAlternatives


def send_email(data: dict[str, Any]) -> dict[str, Any]:
    """
    Send a single email.

    :param data: Dictionary containing email data:
        - subject: Email subject
        - body: Plain text body
        - from_email: Sender email
        - to: List of recipient emails
        - bcc: Optional list of BCC emails
        - cc: Optional list of CC emails
        - reply_to: Optional list of reply-to emails
        - html_content: Optional HTML content
    :return: Dictionary with send status
    """
    msg = EmailMultiAlternatives(
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        from_email=data.get("from_email"),
        to=data.get("to", []),
        bcc=data.get("bcc"),
        cc=data.get("cc"),
        reply_to=data.get("reply_to"),
    )

    # Add HTML alternative if present
    if data.get("html_content"):
        msg.attach_alternative(data["html_content"], "text/html")

    try:
        connection = mail.get_connection()
        sent = connection.send_messages([msg])
        return {"sent": sent > 0, "recipient": data.get("to", [])[0] if data.get("to") else None}
    except Exception as e:
        raise Exception(f"Failed to send email: {e}") from e


def serialize_email_message(msg: EmailMultiAlternatives) -> dict[str, Any]:
    """
    Serialize a single EmailMultiAlternatives object to JSON-compatible dictionary.

    :param msg: EmailMultiAlternatives object
    :return: Serialized email data
    """
    email_data: dict[str, Any] = {
        "subject": msg.subject,
        "body": msg.body,
        "from_email": msg.from_email,
        "to": msg.to,
    }

    if msg.bcc:
        email_data["bcc"] = msg.bcc
    if msg.cc:
        email_data["cc"] = msg.cc
    if msg.reply_to:
        email_data["reply_to"] = msg.reply_to

    # Extract HTML alternative if present
    if msg.alternatives:
        for content, mimetype in msg.alternatives:
            if mimetype == "text/html":
                email_data["html_content"] = content
                break

    return email_data
