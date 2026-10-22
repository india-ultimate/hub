"""Announcements as Markdown for AI agents: what they write becomes the HTML Hub's
editor makes, and what Hub stores reads back as Markdown they can edit.

CommonMark (markdown-it) with strikethrough and line breaks, raw HTML off. The
announcement API cleans the result, as it does the editor's. Reading back walks the
HTML with the standard library's parser.
"""

import re
from collections.abc import Callable, Iterable
from html.parser import HTMLParser

from markdown_it import MarkdownIt

PARSER = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("strikethrough")
MARKS = {"strong": "**", "b": "**", "em": "*", "i": "*", "s": "~~", "del": "~~"}
SPECIAL = re.compile(r"([\\`*_\[\]<>~])")
# Text at the start of a line that Markdown would read as a heading, list or quote.
STARTS_BLOCK = re.compile(r"^(\s*)(#+|[>+-]|\d+[.)])(?=\s|$)", re.MULTILINE)


def markdown(text: str) -> str:
    """Markdown as Hub announcement HTML. A # heading is h2: the post's title is h1."""
    tokens = PARSER.parse(text)
    for token in tokens:
        if token.type in ("heading_open", "heading_close") and token.tag == "h1":
            token.tag = "h2"
    html = PARSER.renderer.render(tokens, PARSER.options, {})
    # As the editor writes it: no line breaks between tags (code keeps its own, escaped).
    return re.sub(r"(?<=>)\n(?=<)", "", html.replace("<br />\n", "<br>")).strip()


class Tag:
    """An element of a post's HTML: its name, attributes and children."""

    def __init__(self, name: str, attrs: dict[str, str | None]) -> None:
        self.name, self.attrs = name, attrs
        self.children: list[Tag | str] = []

    def get(self, key: str) -> str | None:
        return self.attrs.get(key)

    def get_text(self) -> str:
        return "".join(c if isinstance(c, str) else c.get_text() for c in self.children)

    def find_all(self, names: str | list[str], recursive: bool = True) -> list["Tag"]:
        wanted = [names] if isinstance(names, str) else names
        found = []
        for child in self.children:
            if isinstance(child, Tag):
                if child.name in wanted:
                    found.append(child)
                if recursive:
                    found.extend(child.find_all(wanted))
        return found


class _Tree(HTMLParser):
    VOID = {"br", "hr", "img", "source", "col", "wbr", "input", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Tag("root", {})
        self.open = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Tag(tag, dict(attrs))
        self.open[-1].children.append(node)
        if tag not in self.VOID:
            self.open.append(node)

    def handle_endtag(self, tag: str) -> None:
        names = [node.name for node in self.open]
        if tag in names[1:]:
            del self.open[len(names) - 1 - names[::-1].index(tag) :]

    def handle_data(self, data: str) -> None:
        self.open[-1].children.append(data)


def to_markdown(content: str) -> str:
    """Hub's stored HTML for an announcement, as Markdown an agent can edit and send back."""
    tree = _Tree()
    tree.feed(content)
    tree.close()
    text = _blocks(tree.root.children, "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _blocks(nodes: Iterable["Tag | str"], indent: str) -> str:
    """Block-level nodes, one blank line apart; loose text and marks between them are
    a paragraph of their own."""
    out: list[str] = []
    run: list[Tag | str] = []

    def flush() -> None:
        if text := _escape_start(_inline(run).strip()):
            out.append("\n".join(indent + line for line in text.split("\n")))
        run.clear()

    for node in nodes:
        if isinstance(node, Tag) and node.name in BLOCK:
            flush()
            if block := BLOCK[node.name](node, indent):
                out.append(block)
        else:
            run.append(node)
    flush()
    return "\n\n".join(out)


def _inline(nodes: Iterable[Tag | str]) -> str:
    parts = []
    for node in nodes:
        if isinstance(node, str):
            parts.append(SPECIAL.sub(r"\\\1", re.sub(r"\s+", " ", node)))
        elif node.name in ("script", "style"):
            continue
        elif node.name == "br":
            parts.append("\n")
        elif node.name in MARKS:
            inner = _inline(node.children)
            lead, core, trail = re.fullmatch(r"(\s*)(.*?)(\s*)", inner, re.S).groups()  # type: ignore[union-attr]
            mark = MARKS[node.name]
            parts.append(f"{lead}{mark}{core}{mark}{trail}" if core else inner)
        elif node.name == "code":
            parts.append(_code_span(node.get_text()))
        elif node.name == "a":
            href = str(node.get("href") or "")
            label = _inline(node.children)
            parts.append(f"[{label}]({_address(href)})" if re.match(r"https?://", href) else label)
        elif node.name == "img":
            parts.append(f"![{node.get('alt') or ''}]({_address(str(node.get('src') or ''))})")
        elif node.name == "video":
            parts.append(f"[video]({_address(str(node.get('src') or ''))})")
        else:
            parts.append(_inline(node.children))
    return "".join(parts)


def _address(url: str) -> str:
    return url if re.fullmatch(r"[^\s()<>]+", url) else f"<{url}>"


def _longest_backticks(code: str) -> int:
    return max((len(run) for run in re.findall(r"`+", code)), default=0)


def _code_span(code: str) -> str:
    fence = "`" * (_longest_backticks(code) + 1)
    pad = " " if code.startswith("`") or code.endswith("`") else ""
    return f"{fence}{pad}{code}{pad}{fence}"


def _escape_start(text: str) -> str:
    return STARTS_BLOCK.sub(lambda m: m[1] + m[2][:-1] + "\\" + m[2][-1], text)


def _heading(node: Tag, indent: str) -> str:
    return indent + "#" * max(int(node.name[1]), 2) + " " + _inline(node.children).strip()


def _paragraph(node: Tag, indent: str) -> str:
    return _blocks(node.children, indent)


def _pre(node: Tag, indent: str) -> str:
    code = node.get_text().rstrip("\n")
    fence = "`" * max(3, _longest_backticks(code) + 1)
    body = "\n".join(indent + line for line in code.split("\n"))
    return f"{indent}{fence}\n{body}\n{indent}{fence}"


def _list(node: Tag, indent: str) -> str:
    number = int(str(node.get("start") or 1))
    items = []
    for item in node.find_all("li", recursive=False):
        marker = f"{number}. " if node.name == "ol" else "- "
        number += 1
        lines = _blocks(item.children, " " * len(marker)).split("\n")
        items.append(
            "\n".join([indent + marker + lines[0].lstrip(), *(indent + line for line in lines[1:])])
        )
    return "\n".join(items)


def _quote(node: Tag, indent: str) -> str:
    inner = _blocks(node.children, "")
    return "\n".join(indent + (f"> {line}" if line else ">") for line in inner.split("\n"))


def _table(node: Tag, indent: str) -> str:
    rows = []
    for row in node.find_all("tr"):
        cells = (_inline(cell.children).strip() for cell in row.find_all(["td", "th"]))
        rows.append(indent + "| " + " | ".join(cells) + " |")
    return "\n".join(rows)


BLOCK: dict[str, Callable[[Tag, str], str]] = {
    **dict.fromkeys(("h1", "h2", "h3", "h4"), _heading),
    "p": _paragraph,
    "div": _paragraph,
    "pre": _pre,
    "ul": _list,
    "ol": _list,
    "blockquote": _quote,
    "table": _table,
    "hr": lambda node, indent: indent + "---",
}
