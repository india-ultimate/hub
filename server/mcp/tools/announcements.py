import hashlib
import html
import re
from typing import Any

from django.utils.html import strip_tags

from server.mcp.confirm import confirm_then
from server.mcp.dispatch import call_api, denied, refuse
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, clip, slug_problem

SHOWN_CHARS = 1500
PAGE_SIZE = 20
MAX_TEXT = 20000
EDITABLE = ("title", "content", "is_members_only", "action_text", "action_url")
# Any tag but the paragraphs and line breaks plain text turns into.
RICH = re.compile(r"<(?!/?(?:p|br)\b)", re.IGNORECASE)
LOCKED = (
    "This post is for members only and the signed-in user has no active membership, so "
    "Hub does not show its content. They can read it on Hub once they are a member."
)


def html_to_text(content: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", content)
    text = re.sub(r'(?is)<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"\2 (\1)", text)
    text = re.sub(r"(?i)<li\b[^>]*>", "- ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(li|tr)>", "\n", text)
    text = re.sub(r"(?i)</(p|div|ul|ol|h[1-6]|blockquote|table)>", "\n\n", text)
    lines = (
        re.sub(r"[ \t\xa0]+", " ", line).strip()
        for line in html.unescape(strip_tags(text)).splitlines()
    )
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


@tool(
    "list_announcements",
    title="List announcements",
    description=(
        "Hub announcements you may see, newest first, 20 a page: slug, title, type, author, "
        "date and whether it is members-only and whether you can read it. Read one with "
        "get_announcement."
    ),
    input_schema={
        "type": "object",
        "properties": {"page": {"type": "integer", "minimum": 1}},
        "additionalProperties": False,
    },
)
def list_announcements(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    response = call_api(ctx, "GET", "/api/announcements/")
    if not response.ok:
        return denied(response)
    page = args.get("page", 1)
    rows = response.data[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    out = {
        "announcements": [
            {
                "slug": a["slug"],
                "title": a["title"],
                "type": a["type"],
                "author": a["author"]["full_name"],
                "created_at": a["created_at"],
                "is_members_only": a["is_members_only"],
                "can_read": a["can_read"],
                "is_published": a["is_published"],
            }
            for a in rows
        ],
        "total": len(response.data),
        "page": page,
        "has_more": page * PAGE_SIZE < len(response.data),
    }
    return ok(cap(out, list_key="announcements", hint="Ask for the next page."))


@tool(
    "get_announcement",
    title="Read an announcement",
    description=(
        "An announcement by slug, as plain text in content_text (the author's words). A "
        "members-only post the user cannot read comes back without content and says why."
    ),
    input_schema={
        "type": "object",
        "properties": {"slug": SLUG_SCHEMA},
        "required": ["slug"],
        "additionalProperties": False,
    },
)
def get_announcement(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(slug=args["slug"]):
        return problem
    response = call_api(ctx, "GET", f"/api/announcements/{args['slug']}")
    if not response.ok:
        return denied(response)
    post = response.data
    text = html_to_text(post["content"])
    out = {
        "slug": post["slug"],
        "title": post["title"],
        "type": post["type"],
        "author": post["author"]["full_name"],
        "created_at": post["created_at"],
        "is_members_only": post["is_members_only"],
        "is_published": post["is_published"],
        "can_read": post["can_read"],
        "content_text": text[:MAX_TEXT],
        "action_text": post["action_text"],
        "action_url": post["action_url"],
        "comment_count": post["comment_count"],
    }
    if len(text) > MAX_TEXT:
        out["truncated"] = f"Showing the first {MAX_TEXT} of {len(text)} characters."
    if not post["can_read"]:
        out["locked"] = LOCKED
    return ok(out)


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks)


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "title": row["title"],
        "is_published": row["is_published"],
        "is_members_only": row["is_members_only"],
    }


@tool(
    "create_announcement_draft",
    title="Draft an announcement",
    description=(
        "Save an unpublished announcement draft. Content is plain text: blank lines start a "
        "new paragraph. Nothing is shown to members until it is published, and emailing it "
        "is done on Hub. Returns the slug."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1, "maxLength": 20000},
            "is_members_only": {"type": "boolean"},
            "action_text": {"type": "string", "maxLength": 100},
            "action_url": {"type": "string", "maxLength": 500},
        },
        "required": ["title", "content"],
        "additionalProperties": False,
    },
    audience=Audience.POSTER,
    writes=True,
)
def create_announcement_draft(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    body = {
        **{k: v for k, v in args.items() if k not in ("confirmation", "content")},
        "content": _paragraphs(args["content"]),
        "is_published": False,
    }
    response = call_api(ctx, "POST", "/api/announcements/", body=body)
    return ok(_summary(response.data)) if response.ok else denied(response)


@tool(
    "publish_announcement",
    title="Publish an announcement",
    description=(
        "Publish a draft announcement so members can read it. It is not emailed; emailing "
        "is done on Hub."
    ),
    input_schema={
        "type": "object",
        "properties": {"slug": SLUG_SCHEMA},
        "required": ["slug"],
        "additionalProperties": False,
    },
    audience=Audience.POSTER,
    writes=True,
    destructive=True,
)
def publish_announcement(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(slug=args["slug"]):
        return problem
    path = f"/api/announcements/{args['slug']}"

    def publish() -> ToolResult:
        response = call_api(ctx, "PUT", path, body={"is_published": True})
        return ok(_summary(response.data)) if response.ok else denied(response)

    current = call_api(ctx, "GET", path)
    if not current.ok:
        return denied(current)
    audience = "members only" if current.data["is_members_only"] else "everyone"
    content = current.data["content"]
    return confirm_then(
        ctx,
        message=(
            f'Publish the announcement "{current.data["title"]}" for {audience} to read? '
            f"It will not be emailed.\n\n{clip(html_to_text(content), SHOWN_CHARS)}"
        ),
        binding={**args, "content_sha256": hashlib.sha256(content.encode()).hexdigest()},
        action=publish,
    )


@tool(
    "update_announcement",
    title="Edit an announcement",
    description=(
        "Change your announcement's title, text, members-only setting or button, or "
        'unpublish it. Send only what changes; action_text and action_url as "" remove the '
        "button. Content is plain text that replaces the whole post, so a post with images, "
        "links or formatting has its text edited on Hub. A draft changes straight away; a "
        "published post asks first. Publish a draft with publish_announcement."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "slug": SLUG_SCHEMA,
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1, "maxLength": 20000},
            "is_members_only": {"type": "boolean"},
            "action_text": {"type": "string", "maxLength": 100},
            "action_url": {"type": "string", "maxLength": 500},
            "unpublish": {"type": "boolean", "description": "true hides a published post."},
        },
        "required": ["slug"],
        "additionalProperties": False,
    },
    audience=Audience.POSTER,
    writes=True,
    destructive=True,
)
def update_announcement(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(slug=args["slug"]):
        return problem
    changes: dict[str, Any] = {k: args[k] for k in EDITABLE if k in args}
    if args.get("unpublish"):
        changes["is_published"] = False
    if not changes:
        return fail(
            "Nothing to change: send a title, content, is_members_only, the button or unpublish."
        )
    path = f"/api/announcements/{args['slug']}"
    current = call_api(ctx, "GET", path)
    if not current.ok:
        return denied(current)
    post = current.data
    if not post["can_manage"]:
        return refuse("only staff and the person who wrote it can change this announcement.")
    button = args.get("action_text", post["action_text"]) or ""
    link = args.get("action_url", post["action_url"]) or ""
    if button and not link:
        return fail("A button needs a link: send action_url too.")
    if "content" in changes:
        if RICH.search(post["content"]):
            return fail(
                "This post has images, links or formatting that plain text would lose. "
                "Edit its text on Hub; the title, audience and button can still change here."
            )
        changes["content"] = _paragraphs(changes["content"])

    def save() -> ToolResult:
        response = call_api(ctx, "PUT", path, body=changes)
        return ok(_summary(response.data)) if response.ok else denied(response)

    if not post["is_published"]:
        return save()
    lines = [f'Change the published announcement "{post["title"]}"? Members can already see it.']
    if "title" in changes:
        lines.append(f"New title: {changes['title']}")
    if "is_members_only" in changes:
        lines.append(f"Readable by: {'members only' if changes['is_members_only'] else 'everyone'}")
    if "action_text" in changes or "action_url" in changes:
        lines.append(f"Button: {button} ({link})" if button else "Button: removed")
    if "is_published" in changes:
        lines.append("It will be hidden from members until it is published again.")
    if "content" in changes:
        lines.append(f"New text:\n\n{clip(args['content'], SHOWN_CHARS)}")
    shown = {k: post[k] for k in EDITABLE}
    return confirm_then(
        ctx,
        message="\n".join(lines),
        binding={**args, "current_sha256": hashlib.sha256(repr(shown).encode()).hexdigest()},
        action=save,
    )
