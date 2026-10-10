"""YouTube publish regression tests — guards the chain fixed in the
production 502 incident (wrong upload host, missing token refresh,
generate_nonce removal, creds fallback).

Mocks httpx at the adapter boundary — no provider calls, no DB.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)
os.environ.setdefault("GOOGLE_CLIENT_ID", "g-client-123")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "g-secret-456")

from prachar_shared.contracts import TokenSet  # noqa: E402
from prachar_shared.adapters.organic import youtube as yt  # noqa: E402


def _tokens() -> TokenSet:
    return TokenSet(
        access_token="ya29.test",
        refresh_token="refresh-abc",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/youtube"],
    )


# ─── credential fallback (set=google creds, empty youtube creds) ────────────


class TestCredentialFallback:
    def test_client_id_falls_back_to_google(self, monkeypatch):
        monkeypatch.setattr(
            yt, "_settings",
            lambda: MagicMock(youtube_client_id="", youtube_client_secret="", google_client_id="G1", google_client_secret="GS"),
        )
        from prachar_shared.config import get_settings
        s = MagicMock(youtube_client_id="", youtube_client_secret="", google_client_id="G1", google_client_secret="GS")
        assert yt._client_id(s) == "G1"
        assert yt._client_secret(s) == "GS"

    def test_explicit_youtube_creds_win(self):
        s = MagicMock(youtube_client_id="Y1", youtube_client_secret="YS", google_client_id="G1", google_client_secret="GS")
        assert yt._client_id(s) == "Y1"
        assert yt._client_secret(s) == "YS"


# ─── resumable upload host + flow ────────────────────────────────────────────


class TestResumableUpload:
    @pytest.mark.asyncio
    async def test_uses_www_host_and_returns_video_id(self, monkeypatch):
        """Regression: upload.googleapis.com returns HTML 404 — must be www."""
        init_resp = MagicMock(status_code=200, headers={"Location": "https://up.example/session"}, text="")
        dl_resp = MagicMock(status_code=200, content=b"VIDEODATA")
        dl_resp.raise_for_status = lambda: None
        put_resp = MagicMock(status_code=200, text='{"id": "yt-video-9"}')
        put_resp.json = lambda: {"id": "yt-video-9"}

        calls = []

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, **k): calls.append(("get", url)); return dl_resp
            async def post(self, url, **k): calls.append(("post", url, k)); return init_resp
            async def put(self, url, **k): calls.append(("put", url)); return put_resp

        monkeypatch.setattr(yt.httpx, "AsyncClient", _Client)
        vid = await yt._upload_video("tok", "https://s3.example/file.mp4", {"title": "t"})
        assert vid == "yt-video-9"
        post_url = calls[1][1]
        assert post_url == "https://www.googleapis.com/upload/youtube/v3/videos"
        assert "upload.googleapis.com/upload" not in post_url

    @pytest.mark.asyncio
    async def test_init_failure_surfaces_body(self, monkeypatch):
        init_resp = MagicMock(status_code=403, headers={}, text='{"error":"quota"}')
        dl_resp = MagicMock(status_code=200, content=b"X")
        dl_resp.raise_for_status = lambda: None

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, url, **k): return dl_resp
            async def post(self, url, **k): return init_resp
            async def put(self, url, **k): raise AssertionError("no put after init failure")

        monkeypatch.setattr(yt.httpx, "AsyncClient", _Client)
        with pytest.raises(RuntimeError, match="upload init failed 403"):
            await yt._upload_video("tok", "https://s3.example/f.mp4", {"title": "t"})


# ─── publish dispatch ────────────────────────────────────────────────────────


class TestPublish:
    def test_requires_video_ref(self):
        adapter = yt.YouTubeAdapter()
        with pytest.raises(ValueError, match="video_url or video_id"):
            adapter.publish(_tokens(), {})

    def test_video_url_path_invokes_upload(self, monkeypatch):
        adapter = yt.YouTubeAdapter()
        monkeypatch.setattr(yt, "_upload_video", AsyncMock(return_value="yt-new-id"))
        ref = adapter.publish(_tokens(), {"video_url": "https://x/f.mp4", "title": "T", "privacy": "public"})
        assert ref.native_id == "yt-new-id"
        assert ref.url == "https://www.youtube.com/watch?v=yt-new-id"


# ─── token refresh ───────────────────────────────────────────────────────────


class TestRefresh:
    def test_posts_refresh_grant_to_google(self, monkeypatch):
        captured = {}

        async def fake_request(method, url, **kw):
            captured.update(method=method, url=url, data=kw.get("data"))
            r = MagicMock(status_code=200)
            r.raise_for_status = lambda: None
            r.json = lambda: {"access_token": "ya29.new", "expires_in": 3600}
            return r

        monkeypatch.setattr(yt, "_request", fake_request)
        adapter = yt.YouTubeAdapter()
        out = adapter.refresh_access_token("refresh-abc")
        assert out.access_token == "ya29.new"
        assert out.refresh_token == "refresh-abc"  # Google omits it when unchanged
        assert captured["url"] == yt._YT_TOKEN_URL
        assert captured["data"]["grant_type"] == "refresh_token"
        assert captured["data"]["refresh_token"] == "refresh-abc"
