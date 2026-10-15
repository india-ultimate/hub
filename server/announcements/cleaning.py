"""What an announcement's HTML may contain: the tags the Hub editor makes."""

import nh3

TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li",
    "blockquote", "hr", "img", "table", "thead", "tbody", "tr", "th", "td", "colgroup", "col",
    "span", "div",
}  # fmt: skip
ATTRIBUTES = {
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "col": {"span"},
}
URL_SCHEMES = {"http", "https", "mailto"}


def _keep_attribute(tag: str, attribute: str, value: str) -> str | None:
    """Relative addresses stay, but not ones that leave the site (`//host`, `\\host`),
    and images take only http(s) addresses, not mailto."""
    if attribute in {"href", "src"}:
        address = value.strip().lower()
        if address.startswith("//") or "\\" in address:
            return None
        if tag == "img" and address.startswith("mailto:"):
            return None
    return value


def clean_content(html: str) -> str:
    return nh3.clean(
        html,
        tags=TAGS,
        attributes=ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer",
        attribute_filter=_keep_attribute,
    )


def is_blank(cleaned: str) -> bool:
    """No text and no picture: the editor's empty `<p></p>` is blank."""
    return "<img" not in cleaned and not nh3.clean(cleaned, tags=set()).strip()
