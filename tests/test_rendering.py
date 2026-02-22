"""Tests for rendering module."""

from ctxclipper.rendering import (
    cdata_wrap,
    join_texts,
    render_block,
    render_section,
    wrap_chunk,
    wrap_files_root,
    xml_escape_attr,
)
from ctxclipper.types import FileBlock


class TestXmlEscapeAttr:
    """Tests for xml_escape_attr function."""

    def test_no_escaping_needed(self) -> None:
        """Plain text should pass through unchanged."""
        assert xml_escape_attr("hello world") == "hello world"

    def test_escape_ampersand(self) -> None:
        """Ampersands should be escaped."""
        assert xml_escape_attr("foo & bar") == "foo &amp; bar"

    def test_escape_quotes(self) -> None:
        """Double quotes should be escaped."""
        assert xml_escape_attr('say "hello"') == "say &quot;hello&quot;"

    def test_escape_angle_brackets(self) -> None:
        """Angle brackets should be escaped."""
        assert xml_escape_attr("<tag>") == "&lt;tag&gt;"

    def test_escape_all(self) -> None:
        """All special characters should be escaped together."""
        assert xml_escape_attr('<a href="x&y">') == "&lt;a href=&quot;x&amp;y&quot;&gt;"


class TestCdataWrap:
    """Tests for cdata_wrap function."""

    def test_simple_wrap(self) -> None:
        """Simple text should be wrapped in CDATA."""
        assert cdata_wrap("hello") == "<![CDATA[hello]]>"

    def test_cdata_end_sequence_escaped(self) -> None:
        """CDATA end sequence should be escaped."""
        result = cdata_wrap("foo]]>bar")
        # The input "]]>" should be split across CDATA sections
        assert result == "<![CDATA[foo]]]]><![CDATA[>bar]]>"
        # Verify the problematic sequence doesn't appear unescaped in the content
        # (excluding the legitimate CDATA wrapper endings)
        content_without_wrapper = result[9:-3]  # Strip <![CDATA[ and ]]>
        assert "]]>" not in content_without_wrapper.replace("]]]]><![CDATA[>", "")

    def test_empty_string(self) -> None:
        """Empty string should produce valid CDATA."""
        assert cdata_wrap("") == "<![CDATA[]]>"


class TestRenderSection:
    """Tests for render_section function."""

    def test_xml_format(self) -> None:
        """XML format should wrap in tags with CDATA."""
        result = render_section("preamble", "Hello", "xml")
        assert "<preamble>" in result
        assert "</preamble>" in result
        assert "<![CDATA[Hello]]>" in result

    def test_legacy_format(self) -> None:
        """Legacy format should use === markers."""
        result = render_section("preamble", "Hello", "legacy")
        assert "=== PREAMBLE ===" in result
        assert "Hello" in result

    def test_empty_text_returns_empty(self) -> None:
        """Empty or None text should return empty string."""
        assert render_section("preamble", "", "xml") == ""
        assert render_section("preamble", None, "xml") == ""


class TestRenderBlock:
    """Tests for render_block function."""

    def test_xml_format(self) -> None:
        """XML format should create proper file element."""
        block = FileBlock(rel_path="src/main.py", raw="print('hello')")
        result = render_block(block, "xml")
        assert '<file path="src/main.py">' in result
        assert "</file>" in result
        assert "<![CDATA[print('hello')]]>" in result

    def test_xml_escapes_path(self) -> None:
        """XML format should escape special chars in path."""
        block = FileBlock(rel_path='path with "quotes"', raw="content")
        result = render_block(block, "xml")
        assert "&quot;" in result

    def test_legacy_format(self) -> None:
        """Legacy format should use === FILE: markers."""
        block = FileBlock(rel_path="src/main.py", raw="print('hello')")
        result = render_block(block, "legacy")
        assert "=== FILE: src/main.py ===" in result
        assert "print('hello')" in result


class TestWrapFilesRoot:
    """Tests for wrap_files_root function."""

    def test_xml_format(self) -> None:
        """XML format should wrap in files element."""
        result = wrap_files_root("content", "xml")
        assert result == "<files>\ncontent\n</files>\n"

    def test_legacy_format(self) -> None:
        """Legacy format should pass through unchanged."""
        result = wrap_files_root("content", "legacy")
        assert result == "content"


class TestWrapChunk:
    """Tests for wrap_chunk function."""

    def test_xml_wrap(self) -> None:
        """XML wrap should add chunk element."""
        result = wrap_chunk("content", 1, 3, "xml", "xml")
        assert '<chunk index="1" total="3">' in result
        assert "</chunk>" in result

    def test_legacy_wrap(self) -> None:
        """Legacy wrap should add chunk marker."""
        result = wrap_chunk("content", 1, 3, "legacy", "legacy")
        assert "=== CHUNK 1/3 ===" in result

    def test_none_wrap(self) -> None:
        """No wrap should pass through unchanged."""
        result = wrap_chunk("content", 1, 3, "none", "xml")
        assert result == "content"


class TestJoinTexts:
    """Tests for join_texts function."""

    def test_join_simple(self) -> None:
        """Simple texts should be joined with double newlines."""
        result = join_texts(["foo", "bar"])
        assert result == "foo\n\nbar"

    def test_strips_trailing_newlines(self) -> None:
        """Trailing newlines should be stripped from parts."""
        result = join_texts(["foo\n\n", "bar\n"])
        assert result == "foo\n\nbar"

    def test_filters_none(self) -> None:
        """None values should be filtered out."""
        result = join_texts(["foo", None, "bar"])
        assert result == "foo\n\nbar"

    def test_empty_list(self) -> None:
        """Empty list should return empty string."""
        result = join_texts([])
        assert result == ""
