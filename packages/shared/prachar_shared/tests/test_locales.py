from __future__ import annotations

import pytest

from prachar_shared.locales import (
    LocalePack,
    REGION_ROUTES,
    SUPPORTED_LOCALES,
    channels_for_region,
    get_locale_pack,
)


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


def test_get_locale_pack_hi_in() -> None:
    pack = get_locale_pack("hi-IN")
    assert pack is not None
    assert isinstance(pack, LocalePack)
    assert pack.language == "hi"
    assert pack.region == "IN"
    assert pack.code == "hi-IN"


def test_channels_for_region_in() -> None:
    channels = channels_for_region("IN")
    assert "whatsapp" in channels
    assert "instagram" in channels


def test_channels_for_region_kr() -> None:
    channels = channels_for_region("KR")
    assert "kakao" in channels


def test_all_14_supported_locales_present() -> None:
    expected = {
        "en-US", "en-GB", "en-IN", "en-AU",
        "hi-IN", "ar-SA", "es-ES", "pt-BR",
        "id-ID", "ja-JP", "ko-KR", "de-DE",
        "fr-FR", "ru-RU",
    }
    assert set(SUPPORTED_LOCALES.keys()) == expected
    assert len(SUPPORTED_LOCALES) == 14


def test_get_locale_pack_unknown_returns_none() -> None:
    assert get_locale_pack("xx-XX") is None


def test_locale_pack_has_required_fields() -> None:
    for code, pack in SUPPORTED_LOCALES.items():
        assert pack.code == code
        assert pack.language
        assert pack.region
        assert pack.cultural_register
        assert isinstance(pack.channels, list)
        assert isinstance(pack.posting_times, list)
        assert pack.hashtag_style


def test_region_routes_keys() -> None:
    for region in ("IN", "KR", "RU", "CIS", "JP", "MENA", "Americas", "Europe"):
        assert region in REGION_ROUTES
        assert REGION_ROUTES[region]


def test_channels_for_region_unknown_returns_empty() -> None:
    assert channels_for_region("ZZ") == []
