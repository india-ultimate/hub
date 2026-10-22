import re

from django.test import SimpleTestCase

from server.announcements.cleaning import clean_content
from server.mcp.markdown import markdown, to_markdown


def tidy(html: str) -> str:
    """HTML as Hub keeps it, written one way: no line breaks next to tags, list items
    without their own paragraph, bold outside italics."""
    kept = clean_content(html).replace(' rel="noopener noreferrer"', "")
    kept = re.sub(r"(?<=>)\n|\n(?=<)", "", kept)
    kept = re.sub(r"<li><p>(.*?)</p>", r"<li>\1", kept)
    return kept.replace("<em><strong>", "<strong><em>").replace("</strong></em>", "</em></strong>")


class TestMarkdown(SimpleTestCase):
    def html(self, text: str) -> str:
        return tidy(markdown(text))

    def test_paragraphs_and_line_breaks(self) -> None:
        self.assertEqual("<p>One<br>two</p><p>Three</p>", self.html("One\ntwo\n\nThree"))

    def test_headings_start_below_the_title(self) -> None:
        self.assertEqual(
            "<h2>Big</h2><h2>Section</h2><h3>Sub</h3>", self.html("# Big\n## Section ##\n### Sub")
        )

    def test_bold_italic_strike_and_inline_code(self) -> None:
        self.assertEqual(
            "<p><strong>Allow</strong>, <em>then</em> <s>not</s> type <code>**raw**</code></p>",
            self.html("**Allow**, *then* ~~not~~ type `**raw**`"),
        )

    def test_words_and_sums_stay_as_written(self) -> None:
        self.assertEqual(
            "<p>call get_team_registration, 5*3</p>", self.html("call get_team_registration, 5*3")
        )

    def test_lists_nest_and_keep_their_numbers(self) -> None:
        self.assertEqual(
            '<ul><li>a<ul><li>b</li></ul></li></ul><ol start="3"><li>c</li></ol>',
            self.html("- a\n  - b\n\n3. c"),
        )

    def test_a_code_block_keeps_everything_inside(self) -> None:
        self.assertEqual(
            "<pre><code>Line **one**\n  &lt;two&gt; ``` x</code></pre><p>After</p>",
            self.html("````\nLine **one**\n  <two> ``` x\n````\nAfter"),
        )

    def test_code_inside_a_link(self) -> None:
        self.assertEqual(
            '<p>See <code>a</code> and <a href="https://x.org"><code>c</code></a></p>',
            self.html("See `a` and [`c`](https://x.org)"),
        )

    def test_html_and_unsafe_links_stay_text(self) -> None:
        self.assertEqual(
            "<p>&lt;b&gt;hi&lt;/b&gt; [x](javascript:alert(1))</p>",
            self.html("<b>hi</b> [x](javascript:alert(1))"),
        )

    def test_windows_line_endings(self) -> None:
        self.assertEqual("<p>a<br>b</p>", self.html("a\r\nb"))


class TestBackToMarkdown(SimpleTestCase):
    # As Hub's editor writes them: list items hold paragraphs.
    POSTS = [
        "<h2>When</h2><p><strong>Sunday</strong>, 6 am at <em>Cubbon Park</em>.<br>Bring water.</p>",
        "<ul><li><p>one</p></li><li><p>two <strong><em>both</em></strong></p></li></ul>",
        '<ol start="3"><li><p>three</p><ul><li><p>nested</p></li></ul></li><li><p>four</p></li></ol>',
        "<pre><code>paste ``` this\n  exactly</code></pre><p>Use <code>a`b</code></p>",
        '<blockquote><p>Said <a href="https://x.org/a_b">this</a></p></blockquote><hr><p>end</p>',
        "<p>1. not a list, # not a heading, - not a bullet, a*b_c</p>",
    ]

    def test_hub_posts_survive_a_round_trip(self) -> None:
        for post in self.POSTS:
            with self.subTest(post=post):
                self.assertEqual(tidy(post), tidy(markdown(to_markdown(post))))

    def test_a_post_reads_as_markdown(self) -> None:
        self.assertEqual(
            "## When\n\n**Sunday**, 6 am at *Cubbon Park*.\nBring water.",
            to_markdown(self.POSTS[0]),
        )

    def test_media_and_tables_are_shown_not_lost_silently(self) -> None:
        text = to_markdown(
            '<p>x</p><img src="https://a.org/p.png" alt="pic"><video src="https://a.org/v.mp4">'
            "</video><table><tr><td>a</td><td>b</td></tr></table><script>no</script>"
        )

        self.assertIn("![pic](https://a.org/p.png)", text)
        self.assertIn("[video](https://a.org/v.mp4)", text)
        self.assertIn("| a | b |", text)
        self.assertNotIn("no", text)
