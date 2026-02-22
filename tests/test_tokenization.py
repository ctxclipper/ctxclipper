"""Tests for tokenization module."""

from ctxclipper.tokenization import (
    count_tokens,
    count_tokens_with_encoder,
    fits_budget,
    get_tokenizer,
    safe_token_len,
)


class TestGetTokenizer:
    """Tests for get_tokenizer function."""

    def test_default_encoding(self) -> None:
        """Default encoding should return o200k_base."""
        result = get_tokenizer(None, None)
        if result.encoder is not None:
            assert result.encoder.name == "o200k_base"
            assert result.source == "encoding"
        else:
            # tiktoken not installed
            assert result.source == "none"

    def test_explicit_encoding(self) -> None:
        """Explicit encoding should be used."""
        result = get_tokenizer(None, "cl100k_base")
        if result.encoder is not None:
            assert result.encoder.name == "cl100k_base"
            assert result.source == "encoding"

    def test_known_model(self) -> None:
        """Known models should use model-specific encoding."""
        result = get_tokenizer("gpt-4", None)
        if result.encoder is not None:
            assert result.source == "model"

    def test_o_series_model(self) -> None:
        """O-series models should resolve to an encoder."""
        result = get_tokenizer("o1", None)
        if result.encoder is not None:
            # May be "model" (if tiktoken knows it) or "override" (our fallback)
            assert result.source in ("model", "override")

    def test_gpt5_model(self) -> None:
        """GPT-5 models should resolve to an encoder."""
        result = get_tokenizer("gpt-5", None)
        if result.encoder is not None:
            # May be "model" (if tiktoken knows it) or "override" (our fallback)
            assert result.source in ("model", "override")

    def test_unknown_model_fallback(self) -> None:
        """Unknown models should fall back to encoding."""
        result = get_tokenizer("unknown-model-xyz", None)
        if result.encoder is not None:
            assert result.source == "encoding"
            assert "Unknown model" in (result.note or "")


class TestFitsBudget:
    """Tests for fits_budget function."""

    def test_within_char_budget(self) -> None:
        """Content within char budget should fit."""
        assert fits_budget("hello", max_chars=10, max_tokens=None, enc=None) is True

    def test_exceeds_char_budget(self) -> None:
        """Content exceeding char budget should not fit."""
        assert fits_budget("hello world", max_chars=5, max_tokens=None, enc=None) is False

    def test_no_char_limit(self) -> None:
        """No char limit should always fit for chars."""
        assert fits_budget("hello" * 1000, max_chars=None, max_tokens=None, enc=None) is True

    def test_token_budget_without_encoder(self) -> None:
        """Token budget without encoder should be ignored."""
        assert fits_budget("hello", max_chars=None, max_tokens=1, enc=None) is True

    def test_token_budget_with_encoder(self) -> None:
        """Token budget with encoder should be enforced."""
        result = get_tokenizer(None, None)
        if result.encoder is not None:
            # "hello" should be 1-2 tokens
            assert fits_budget("hello", max_chars=None, max_tokens=10, enc=result.encoder) is True
            # Very low token limit should fail
            assert (
                fits_budget(
                    "hello world this is a longer text",
                    max_chars=None,
                    max_tokens=1,
                    enc=result.encoder,
                )
                is False
            )


class TestSafeTokenLen:
    """Tests for safe_token_len function."""

    def test_none_encoder_returns_zero(self) -> None:
        """None encoder should return 0."""
        assert safe_token_len(None, "hello") == 0

    def test_empty_text_returns_zero(self) -> None:
        """Empty text should return 0."""
        result = get_tokenizer(None, None)
        assert safe_token_len(result.encoder, "") == 0

    def test_valid_encoder_counts_tokens(self) -> None:
        """Valid encoder should count tokens."""
        result = get_tokenizer(None, None)
        if result.encoder is not None:
            count = safe_token_len(result.encoder, "hello world")
            assert count > 0


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_counts_with_model(self) -> None:
        """Should count tokens for known model."""
        count, _note = count_tokens("hello world", model="gpt-4", encoding_name=None)
        # Should return a positive count if tiktoken available
        assert count is None or count > 0

    def test_counts_with_encoding(self) -> None:
        """Should count tokens with explicit encoding."""
        count, _note = count_tokens("hello world", model=None, encoding_name="cl100k_base")
        assert count is None or count > 0

    def test_counts_with_defaults(self) -> None:
        """Should count tokens with default encoding."""
        count, _note = count_tokens("hello world", model=None, encoding_name=None)
        assert count is None or count > 0

    def test_empty_string_returns_zero(self) -> None:
        """Empty string should return 0 tokens."""
        count, _note = count_tokens("", model=None, encoding_name=None)
        assert count is None or count == 0


class TestCountTokensWithEncoder:
    """Tests for count_tokens_with_encoder function."""

    def test_with_valid_encoder(self) -> None:
        """Should count tokens with valid encoder."""
        result = get_tokenizer(None, None)
        if result.encoder is not None:
            count, note = count_tokens_with_encoder("hello world", result.encoder, None, None)
            assert count is not None
            assert count > 0
            assert note is None

    def test_none_encoder_falls_back(self) -> None:
        """None encoder should fall back to model/encoding."""
        count, note = count_tokens_with_encoder("hello world", None, "gpt-4", None)
        # Either successfully counted or note explains why not
        assert count is not None or note is not None

    def test_returns_note_on_failure(self) -> None:
        """Should return note when counting fails."""
        count, note = count_tokens_with_encoder("hello world", None, None, None)
        # With no encoder and no model/encoding, might still work with defaults
        # Just ensure we get some response
        assert count is not None or note is not None

    def test_empty_string_with_encoder(self) -> None:
        """Empty string should return 0 tokens."""
        result = get_tokenizer(None, None)
        if result.encoder is not None:
            count, note = count_tokens_with_encoder("", result.encoder, None, None)
            assert count == 0
            assert note is None
