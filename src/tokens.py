"""
Custom token management for Flux2 Klein LoRA fine-tuning.

Handles trigger tokens, pose tokens, style tokens, and any other custom tokens
that control specific aspects of generation during inference.

Token categories:
- trigger: Main concept/identity token (e.g., <tmp>)
- pose: Viewpoint/perspective tokens (e.g., <pose-topdown>)
- style: Visual style tokens (e.g., <style-steampunk>)
- asset: Asset type tokens (e.g., <asset-structure>, <asset-tile>)
- custom: User-defined freeform tokens
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Regex for custom tokens: <alphanumeric-hyphen> format
_TOKEN_PATTERN = re.compile(r"<[a-zA-Z][a-zA-Z0-9_-]*>")


@dataclass
class TokenDef:
    """Definition of a single custom token."""
    value: str
    category: str = "custom"
    description: str = ""
    required: bool = False


@dataclass
class TokenConfig:
    """Complete token configuration for a training run."""
    trigger: Optional[TokenDef] = None
    pose: Optional[TokenDef] = None
    style: Optional[TokenDef] = None
    asset: Optional[TokenDef] = None
    custom: List[TokenDef] = field(default_factory=list)
    prepend_to_captions: bool = True
    validate_presence: bool = True

    def all_tokens(self) -> List[TokenDef]:
        """Return all defined tokens in priority order (trigger first)."""
        tokens: List[TokenDef] = []
        if self.trigger is not None:
            tokens.append(self.trigger)
        if self.pose is not None:
            tokens.append(self.pose)
        if self.style is not None:
            tokens.append(self.style)
        if self.asset is not None:
            tokens.append(self.asset)
        tokens.extend(self.custom)
        return tokens

    def required_tokens(self) -> List[TokenDef]:
        """Return tokens that must be present in captions."""
        return [t for t in self.all_tokens() if t.required]

    def token_values(self) -> List[str]:
        """Return just the token strings."""
        return [t.value for t in self.all_tokens()]


def parse_token_config(data_cfg: Dict[str, Any]) -> TokenConfig:
    """
    Parse token configuration from data.yaml dict.

    Supports both legacy flat format and new structured format.

    Legacy format (still supported):
        trigger_token: "<tmp>"
        prepend_trigger_token: false

    New structured format:
        tokens:
          trigger: "<tmp>"
          pose: "<pose-topdown>"
          style: null
          asset: null
          custom: []
          prepend_to_captions: true
          validate_presence: true
    """
    tokens_block = data_cfg.get("tokens")
    if isinstance(tokens_block, dict):
        return _parse_structured_tokens(tokens_block)

    # Legacy format: single trigger_token + prepend_trigger_token
    trigger_value = str(data_cfg.get("trigger_token", "")).strip()
    prepend = bool(data_cfg.get("prepend_trigger_token", False))

    trigger = None
    if trigger_value:
        trigger = TokenDef(value=trigger_value, category="trigger", required=True)

    return TokenConfig(
        trigger=trigger,
        prepend_to_captions=prepend,
        validate_presence=bool(trigger_value),
    )


def _parse_structured_tokens(block: Dict[str, Any]) -> TokenConfig:
    """Parse the new structured tokens: { ... } block."""

    def _make_token(raw: Any, category: str, *, required: bool = False) -> Optional[TokenDef]:
        if raw is None:
            return None
        if isinstance(raw, str):
            val = raw.strip()
            return TokenDef(value=val, category=category, required=required) if val else None
        if isinstance(raw, dict):
            val = str(raw.get("value", "")).strip()
            if not val:
                return None
            return TokenDef(
                value=val,
                category=str(raw.get("category", category)),
                description=str(raw.get("description", "")),
                required=bool(raw.get("required", required)),
            )
        return None

    trigger = _make_token(block.get("trigger"), "trigger", required=True)
    pose = _make_token(block.get("pose"), "pose")
    style = _make_token(block.get("style"), "style")
    asset = _make_token(block.get("asset"), "asset")

    custom: List[TokenDef] = []
    raw_custom = block.get("custom")
    if isinstance(raw_custom, list):
        for item in raw_custom:
            td = _make_token(item, "custom")
            if td is not None:
                custom.append(td)

    return TokenConfig(
        trigger=trigger,
        pose=pose,
        style=style,
        asset=asset,
        custom=custom,
        prepend_to_captions=bool(block.get("prepend_to_captions", True)),
        validate_presence=bool(block.get("validate_presence", True)),
    )


def extract_tokens_from_text(text: str) -> Set[str]:
    """Extract all <token> patterns from a caption string."""
    return set(_TOKEN_PATTERN.findall(text))


def caption_has_token(caption: str, token: str) -> bool:
    """Check if a caption contains a specific token."""
    return token.strip() in caption


def caption_has_all_tokens(caption: str, tokens: List[str]) -> bool:
    """Check if a caption contains ALL specified tokens."""
    return all(caption_has_token(caption, t) for t in tokens)


def prepend_tokens_to_caption(caption: str, tokens: List[str]) -> str:
    """
    Prepend tokens to a caption, avoiding duplicates.

    Tokens are prepended in the order given (typically trigger first).
    If a token already appears in the caption, it is not duplicated.
    """
    cleaned = " ".join(caption.strip().split())
    existing = extract_tokens_from_text(cleaned)

    to_prepend: List[str] = []
    for token in tokens:
        tok = token.strip()
        if tok and tok not in existing:
            to_prepend.append(tok)

    if not to_prepend:
        return cleaned

    prefix = " ".join(to_prepend)
    return f"{prefix} {cleaned}"


def strip_tokens_from_caption(caption: str, tokens: Optional[List[str]] = None) -> str:
    """
    Remove tokens from a caption.

    If tokens list is provided, only remove those specific tokens.
    If tokens is None, remove ALL <token> patterns.
    """
    if tokens is None:
        result = _TOKEN_PATTERN.sub("", caption)
    else:
        result = caption
        for token in tokens:
            result = result.replace(token.strip(), "")
    return " ".join(result.strip().split())


def format_prompt_with_tokens(base_prompt: str, token_config: TokenConfig) -> str:
    """
    Format a prompt for inference by ensuring all required tokens are present.
    Used when generating validation/evaluation prompts.
    """
    tokens_to_ensure = [t.value for t in token_config.all_tokens()]
    return prepend_tokens_to_caption(base_prompt, tokens_to_ensure)
