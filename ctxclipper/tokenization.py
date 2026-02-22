"""Token counting with tiktoken integration."""

import logging
import re
from typing import Optional, Tuple

from .constants import DEFAULT_ENCODING
from .types import Encoder, TokenizerResult

__all__ = [
    "count_tokens",
    "count_tokens_with_encoder",
    "fits_budget",
    "get_tokenizer",
    "safe_token_len",
    "token_len",
]

logger = logging.getLogger(__name__)


def get_tokenizer(model: Optional[str], encoding_name: Optional[str]) -> TokenizerResult:
    """
    Get a tiktoken encoder for the specified model or encoding.

    Attempts resolution in order:
    1. Model name via encoding_for_model()
    2. Special handling for gpt-5.* and o-series models
    3. Explicit encoding name
    4. Default encoding (o200k_base)

    Args:
        model: Model name (e.g., "gpt-4", "o1").
        encoding_name: Explicit encoding name override.

    Returns:
        TokenizerResult with encoder, optional note, and source type.
    """
    try:
        import tiktoken
    except ImportError:
        return TokenizerResult(
            encoder=None,
            note="tiktoken not installed (pip install tiktoken)",
            source="none",
        )

    model_raw = model or ""
    model_norm = model_raw.strip().lower()

    # Try model-specific encoding first
    if model_norm:
        try:
            enc = tiktoken.encoding_for_model(model_raw)
            return TokenizerResult(encoder=enc, note=None, source="model")
        except KeyError:
            pass

        # Handle known model families without explicit tiktoken support
        is_gpt5 = model_norm.startswith("gpt-5") or model_norm.startswith("gpt5")
        is_o_family = re.match(r"^o[134](?:[-.]|$)", model_norm) is not None

        if is_gpt5 or is_o_family:
            try:
                enc = tiktoken.get_encoding("o200k_base")
                family = "gpt-5.*" if is_gpt5 else "o-series"
                note = f"tiktoken lacks {family} mapping; using o200k_base"
                return TokenizerResult(encoder=enc, note=note, source="override")
            except Exception as e:
                return TokenizerResult(
                    encoder=None,
                    note=f"Tokenization failed: {e}",
                    source="none",
                )

    # Fall back to explicit encoding
    try:
        enc = tiktoken.get_encoding(encoding_name or DEFAULT_ENCODING)
        fallback_note: Optional[str] = None
        if model_norm:
            fallback_note = f"Unknown model '{model_raw}', used encoding '{enc.name}'"
        return TokenizerResult(encoder=enc, note=fallback_note, source="encoding")
    except Exception as e:
        return TokenizerResult(
            encoder=None,
            note=f"Tokenization failed: {e}",
            source="none",
        )


def count_tokens(
    text: str, model: Optional[str], encoding_name: Optional[str]
) -> Tuple[Optional[int], Optional[str]]:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to tokenize.
        model: Model name for encoding selection.
        encoding_name: Fallback encoding name.

    Returns:
        Tuple of (token_count or None, error_note or None).
    """
    try:
        import tiktoken
    except ImportError:
        return None, "tiktoken not installed (pip install tiktoken)"

    try:
        if model:
            enc = tiktoken.encoding_for_model(model)
        else:
            enc = tiktoken.get_encoding(encoding_name or DEFAULT_ENCODING)
        return len(enc.encode(text)), None
    except KeyError:
        try:
            enc = tiktoken.get_encoding(encoding_name or DEFAULT_ENCODING)
            return len(
                enc.encode(text)
            ), f"Unknown model '{model}', used encoding '{encoding_name or DEFAULT_ENCODING}'"
        except Exception as e:
            return None, f"Tokenization failed: {e}"
    except Exception as e:
        return None, f"Tokenization failed: {e}"


def count_tokens_with_encoder(
    text: str, enc: Encoder, model: Optional[str], encoding_name: Optional[str]
) -> Tuple[Optional[int], Optional[str]]:
    """
    Count tokens using a pre-initialized encoder, with fallback.

    Args:
        text: Text to tokenize.
        enc: Pre-initialized encoder (can be None).
        model: Model name for fallback.
        encoding_name: Encoding name for fallback.

    Returns:
        Tuple of (token_count or None, error_note or None).
    """
    if enc is not None:
        return len(enc.encode(text)), None
    return count_tokens(text, model, encoding_name)


def token_len(enc: Encoder, text: str) -> int:
    """
    Get token length of text using encoder.

    Args:
        enc: Tiktoken encoder (must not be None).
        text: Text to tokenize.

    Returns:
        Number of tokens.
    """
    if enc is None:
        raise ValueError("Encoder is None")
    return len(enc.encode(text))


def safe_token_len(enc: Encoder, text: str) -> int:
    """
    Get token length, returning 0 if encoder is None or text is empty.

    Args:
        enc: Tiktoken encoder (can be None).
        text: Text to tokenize.

    Returns:
        Number of tokens, or 0 if cannot tokenize.
    """
    if enc is None or not text:
        return 0
    return len(enc.encode(text))


def fits_budget(
    rendered: str,
    *,
    max_chars: Optional[int],
    max_tokens: Optional[int],
    enc: Encoder,
) -> bool:
    """
    Check if rendered content fits within budget constraints.

    Args:
        rendered: The rendered text to check.
        max_chars: Maximum character count (None = no limit).
        max_tokens: Maximum token count (None = no limit).
        enc: Tiktoken encoder (can be None).

    Returns:
        True if content fits within all specified budgets.
    """
    if max_chars is not None and len(rendered) > max_chars:
        return False
    if max_tokens is not None and enc is not None and token_len(enc, rendered) > max_tokens:
        return False
    return True
