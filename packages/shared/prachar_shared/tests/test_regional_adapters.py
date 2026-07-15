from __future__ import annotations

import pytest

from prachar_shared.adapters.organic.line import LINEAdapter
from prachar_shared.adapters.organic.naver import NaverAdapter
from prachar_shared.adapters.organic.reddit import RedditAdapter
from prachar_shared.adapters.organic.telegram import TelegramAdapter
from prachar_shared.adapters.organic.vk import VKAdapter
from prachar_shared.adapters.organic.whatsapp import WhatsAppAdapter
from prachar_shared.contracts import PolicyResult


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------
def test_whatsapp_channel() -> None:
    assert WhatsAppAdapter().channel == "whatsapp"


def test_whatsapp_schema_keys() -> None:
    schema = WhatsAppAdapter().generate_schema()
    props = schema["properties"]
    assert "to_phone" in props
    assert "template_name" in props
    assert "template_language" in props
    assert "components" in props
    assert "media_type" in props
    assert "media_url" in props


def test_whatsapp_policy_gate_valid() -> None:
    result = WhatsAppAdapter().policy_gate({
        "to_phone": "+919999999999",
        "template_name": "order_update",
        "template_language": "en_US",
        "components": [],
        "opted_in": True,
    })
    assert isinstance(result, PolicyResult)
    assert result.passed is True


def test_whatsapp_policy_gate_no_optin() -> None:
    result = WhatsAppAdapter().policy_gate({
        "to_phone": "+919999999999",
        "template_name": "order_update",
        "template_language": "en_US",
        "components": [],
        "opted_in": False,
    })
    assert result.passed is False
    assert any("opted-in" in r for r in result.blocked_reasons)


def test_whatsapp_policy_gate_no_template() -> None:
    result = WhatsAppAdapter().policy_gate({
        "to_phone": "+919999999999",
        "template_name": "",
        "template_language": "en_US",
        "components": [],
        "opted_in": True,
    })
    assert result.passed is False
    assert any("template" in r for r in result.blocked_reasons)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def test_telegram_channel() -> None:
    assert TelegramAdapter().channel == "telegram"


def test_telegram_schema_keys() -> None:
    schema = TelegramAdapter().generate_schema()
    props = schema["properties"]
    assert "chat_id" in props
    assert "text" in props
    assert "parse_mode" in props
    assert "reply_markup" in props
    assert "media_url" in props
    assert "media_type" in props


def test_telegram_policy_gate_valid() -> None:
    result = TelegramAdapter().policy_gate({"chat_id": "123", "text": "Hello world"})
    assert isinstance(result, PolicyResult)
    assert result.passed is True


def test_telegram_policy_gate_too_long() -> None:
    result = TelegramAdapter().policy_gate({"chat_id": "123", "text": "A" * 4097})
    assert result.passed is False
    assert any("4096" in r for r in result.blocked_reasons)


# ---------------------------------------------------------------------------
# LINE
# ---------------------------------------------------------------------------
def test_line_channel() -> None:
    assert LINEAdapter().channel == "line"


def test_line_schema_keys() -> None:
    schema = LINEAdapter().generate_schema()
    props = schema["properties"]
    assert "to" in props
    assert "messages" in props
    msg_props = props["messages"]["items"]["properties"]
    assert "type" in msg_props
    assert "text" in msg_props
    assert "originalContentUrl" in msg_props


def test_line_policy_gate_valid() -> None:
    result = LINEAdapter().policy_gate({
        "to": "U123",
        "messages": [{"type": "text", "text": "Hello"}],
    })
    assert isinstance(result, PolicyResult)
    assert result.passed is True


def test_line_policy_gate_no_recipient() -> None:
    result = LINEAdapter().policy_gate({
        "to": "",
        "messages": [{"type": "text", "text": "Hello"}],
    })
    assert result.passed is False


# ---------------------------------------------------------------------------
# VK
# ---------------------------------------------------------------------------
def test_vk_channel() -> None:
    assert VKAdapter().channel == "vk"


def test_vk_schema_keys() -> None:
    schema = VKAdapter().generate_schema()
    props = schema["properties"]
    assert "owner_id" in props
    assert "message" in props
    assert "attachments" in props
    assert "from_group" in props
    assert "publish_date" in props


def test_vk_policy_gate_valid() -> None:
    result = VKAdapter().policy_gate({"owner_id": "-1", "message": "Hello world"})
    assert isinstance(result, PolicyResult)
    assert result.passed is True


def test_vk_policy_gate_no_owner() -> None:
    result = VKAdapter().policy_gate({"owner_id": "", "message": "Hello world"})
    assert result.passed is False


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------
def test_reddit_channel() -> None:
    assert RedditAdapter().channel == "reddit"


def test_reddit_schema_keys() -> None:
    schema = RedditAdapter().generate_schema()
    props = schema["properties"]
    assert "subreddit" in props
    assert "title" in props
    assert "kind" in props
    assert props["kind"]["enum"] == ["link", "self", "image"]
    assert "text" in props
    assert "url" in props
    assert "flair_id" in props
    assert "nsfw" in props
    assert "spoiler" in props


def test_reddit_policy_gate_always_blocks() -> None:
    # Reddit requires human approval — policy_gate always returns passed=False.
    result = RedditAdapter().policy_gate({
        "subreddit": "test",
        "title": "A genuinely useful post",
        "kind": "self",
        "text": "Sharing knowledge with the community",
    })
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("human approval" in w for w in result.warnings)


def test_reddit_policy_gate_valid_still_blocks() -> None:
    # Even valid content is blocked from auto-publish.
    result = RedditAdapter().policy_gate({
        "subreddit": "test",
        "title": "Great discussion",
        "kind": "self",
        "text": "Let's talk about this topic",
    })
    assert result.passed is False
    assert any("human approval" in w for w in result.warnings)


def test_reddit_policy_gate_promo_spam() -> None:
    result = RedditAdapter().policy_gate({
        "subreddit": "test",
        "title": "buy now limited time offer",
        "kind": "self",
        "text": "click here for discount code",
    })
    assert result.passed is False
    assert any("spam" in r for r in result.blocked_reasons)


# ---------------------------------------------------------------------------
# Naver
# ---------------------------------------------------------------------------
def test_naver_channel() -> None:
    assert NaverAdapter().channel == "naver"


def test_naver_schema_keys() -> None:
    schema = NaverAdapter().generate_schema()
    props = schema["properties"]
    assert "title" in props
    assert "content" in props
    assert "tags" in props
    assert "category" in props


def test_naver_policy_gate_valid() -> None:
    result = NaverAdapter().policy_gate({
        "title": "테스트 제목",
        "content": "테스트 내용입니다",
    })
    assert isinstance(result, PolicyResult)
    assert result.passed is True


def test_naver_policy_gate_long_title() -> None:
    result = NaverAdapter().policy_gate({
        "title": "A" * 101,
        "content": "content",
    })
    assert result.passed is False
    assert any("100" in r for r in result.blocked_reasons)
