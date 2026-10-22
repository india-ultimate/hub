import hashlib
import re
from typing import Any

from server.announcements.models import Announcement
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import call_api, denied, refuse
from server.mcp.markdown import markdown, to_markdown
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, clip, slug_problem

SHOWN_CHARS = 1500
PAGE_SIZE = 20
MAX_TEXT = 20000
EDITABLE = ("title", "content", "type", "is_members_only", "action_text", "action_url")
TYPE = {"type": "string", "enum": Announcement.Type.values, "description": "The post's tag."}
# What Markdown can't say, so new text would drop it.
MEDIA = re.compile(r"<(?:img|video|source|table|u)\b", re.IGNORECASE)
MARKDOWN = (
    "Content is Markdown: # headings, **bold**, *italics*, - lists, 1. lists, > quotes, "
    "[links](https://...), `code` and ``` code blocks; blank lines start a new paragraph."
)
LOCKED = (
    "This post is for members only and the signed-in user has no active membership, so "
    "Hub does not show its content. They can read it on Hub once they are a member."
)


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
        "An announcement by slug, its text as Markdown in content_markdown (the author's "
        "words), the same Markdown the draft and edit tools take. A members-only post the "
        "user cannot read comes back without content and says why."
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
    text = to_markdown(post["content"])
    out = {
        "slug": post["slug"],
        "title": post["title"],
        "type": post["type"],
        "author": post["author"]["full_name"],
        "created_at": post["created_at"],
        "is_members_only": post["is_members_only"],
        "is_published": post["is_published"],
        "can_read": post["can_read"],
        "content_markdown": text[:MAX_TEXT],
        "action_text": post["action_text"],
        "action_url": post["action_url"],
        "comment_count": post["comment_count"],
    }
    if len(text) > MAX_TEXT:
        out["truncated"] = f"Showing the first {MAX_TEXT} of {len(text)} characters."
    if not post["can_read"]:
        out["locked"] = LOCKED
    return ok(out)


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
        f"Save an unpublished announcement draft. {MARKDOWN} Pictures and videos are added "
        "on Hub. Nothing is shown to members until it is published, and emailing it is done "
        "on Hub. Returns the slug."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1, "maxLength": 20000},
            "type": TYPE,
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
        "content": markdown(args["content"]),
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
            f"It will not be emailed.\n\n{clip(to_markdown(content), SHOWN_CHARS)}"
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
        f"button. {MARKDOWN} It replaces the whole text, so a post with pictures, videos or "
        "tables or underlining has its text edited on Hub. A draft changes straight away; a published post "
        "asks first. Publish a draft with publish_announcement."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "slug": SLUG_SCHEMA,
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1, "maxLength": 20000},
            "type": TYPE,
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
        if MEDIA.search(post["content"]):
            return fail(
                "This post has pictures, videos, tables or underlining that new text would lose. Edit its "
                "text on Hub; the title, audience and button can still change here."
            )
        changes["content"] = markdown(changes["content"])

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
    if "type" in changes:
        lines.append(f"Tag: {Announcement.Type(changes['type']).label}")
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
