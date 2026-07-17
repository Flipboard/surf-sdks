"""Unit tests for the longform namespace (documents & publications) — no live API.

Verifies the API contract: AT-URIs percent-encoded as a single path segment,
`format` passthrough/omission, repeatable `tags` param, and the Python
`offset` kwarg mapping to the API's reserved-word `from` query param.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock

import pytest

from surf_api import SurfClient
from surf_api.models import Post, DocumentSummary

BASE = "https://api.surf.social/v1"
DOC_URI = "at://did:plc:x/site.standard.document/3k2a"
DOC_URI_ENC = "at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.document%2F3k2a"
PUB_URI = "at://did:plc:x/site.standard.publication/self"
PUB_URI_ENC = "at%3A%2F%2Fdid%3Aplc%3Ax%2Fsite.standard.publication%2Fself"


def _mk_resp(status_code=200, json_body=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _capture(client, json_body=None):
    """Patch the client's session and return the mock so we can inspect calls."""
    return patch.object(client._session, "request", return_value=_mk_resp(json_body=json_body))


def _client():
    return SurfClient(api_key="k")


# ==========================================================================
# Documents
# ==========================================================================

class TestDocument:
    def test_at_uri_is_encoded_as_single_path_segment(self):
        c = _client()
        with _capture(c) as m:
            c.longform.document(DOC_URI)
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/documents/{DOC_URI_ENC}"

    def test_format_omitted_when_none(self):
        c = _client()
        with _capture(c) as m:
            c.longform.document(DOC_URI)
        assert "format" not in (m.call_args.kwargs.get("params") or {})

    def test_format_blocks_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.longform.document(DOC_URI, format="blocks")
        assert m.call_args.kwargs["params"] == {"format": "blocks"}

    def test_format_html_passed_through(self):
        c = _client()
        with _capture(c) as m:
            c.longform.document(DOC_URI, format="html")
        assert m.call_args.kwargs["params"] == {"format": "html"}

    def test_returns_parsed_response(self):
        sample = {"id": DOC_URI, "title": "Hello", "comments_count": 3,
                  "content_html": "<p>Hi</p>"}
        c = _client()
        with _capture(c, json_body=sample):
            assert c.longform.document(DOC_URI) == sample


# ==========================================================================
# Publications
# ==========================================================================

class TestPublication:
    def test_at_uri_is_encoded_as_single_path_segment(self):
        c = _client()
        with _capture(c) as m:
            c.longform.publication(PUB_URI)
        method, url = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert url == f"{BASE}/publications/{PUB_URI_ENC}"


class TestPublicationDocuments:
    def test_path_and_default_params(self):
        c = _client()
        with _capture(c) as m:
            c.longform.publication_documents(PUB_URI)
        url = m.call_args.args[1]
        assert url == f"{BASE}/publications/{PUB_URI_ENC}/documents"
        params = m.call_args.kwargs["params"]
        assert params == {"count": 20, "from": 0}
        assert "tags" not in params  # omitted when None

    def test_tags_sent_as_repeatable_list(self):
        c = _client()
        with _capture(c) as m:
            c.longform.publication_documents(PUB_URI, tags=["essays", "tech"])
        assert m.call_args.kwargs["params"]["tags"] == ["essays", "tech"]

    def test_offset_maps_to_from_param(self):
        c = _client()
        with _capture(c) as m:
            c.longform.publication_documents(PUB_URI, count=50, offset=40)
        params = m.call_args.kwargs["params"]
        assert params["count"] == 50
        assert params["from"] == 40
        assert "offset" not in params


# ==========================================================================
# Publication search (longform namespace + search namespace helper)
# ==========================================================================

class TestSearchPublications:
    def test_longform_search_publications(self):
        c = _client()
        with _capture(c) as m:
            c.longform.search_publications("climate")
        assert m.call_args.args[1] == f"{BASE}/search/publications"
        assert m.call_args.kwargs["params"] == {"q": "climate", "count": 20, "from": 0}

    def test_longform_search_publications_offset_maps_to_from(self):
        c = _client()
        with _capture(c) as m:
            c.longform.search_publications("climate", count=5, offset=10)
        assert m.call_args.kwargs["params"] == {"q": "climate", "count": 5, "from": 10}

    def test_search_namespace_publications_helper(self):
        c = _client()
        with _capture(c) as m:
            c.search.publications("climate", count=5, offset=10)
        assert m.call_args.args[0] == "GET"
        assert m.call_args.args[1] == f"{BASE}/search/publications"
        assert m.call_args.kwargs["params"] == {"q": "climate", "count": 5, "from": 10}


# ==========================================================================
# Models: Post.document summary
# ==========================================================================

class TestPostDocumentModel:
    def test_post_parses_document_summary(self):
        post = Post.from_dict({
            "id": "1",
            "document": {
                "title": "Deep Dive",
                "description": "A longform piece",
                "cover_image_url": "https://cdn.example.com/cover.jpg",
                "tags": ["essays"],
                "publication_uri": PUB_URI,
            },
        })
        assert isinstance(post.document, DocumentSummary)
        assert post.document.title == "Deep Dive"
        assert post.document.tags == ["essays"]
        assert post.document.publication_uri == PUB_URI

    def test_post_document_defaults_to_none(self):
        assert Post.from_dict({"id": "1"}).document is None


# ==========================================================================
# Async client mirrors the sync surface
# ==========================================================================

class TestAsyncLongform:
    @staticmethod
    def _async_client_and_mock(json_body=None):
        pytest.importorskip("httpx")
        import asyncio
        from unittest.mock import AsyncMock
        from surf_api.async_client import AsyncSurfClient

        c = AsyncSurfClient(api_key="k")
        m = AsyncMock(return_value=_mk_resp(json_body=json_body))
        c._client.request = m
        return c, m, asyncio

    def test_document_encodes_at_uri_and_omits_none_format(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.longform.document(DOC_URI))
        method, path = m.call_args.args[0], m.call_args.args[1]
        assert method == "GET"
        assert path == f"/documents/{DOC_URI_ENC}"
        assert "format" not in (m.call_args.kwargs.get("params") or {})
        asyncio.run(c.close())

    def test_document_format_passed_through(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.longform.document(DOC_URI, format="blocks"))
        assert m.call_args.kwargs["params"] == {"format": "blocks"}
        asyncio.run(c.close())

    def test_publication_encodes_at_uri(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.longform.publication(PUB_URI))
        assert m.call_args.args[1] == f"/publications/{PUB_URI_ENC}"
        asyncio.run(c.close())

    def test_publication_documents_tags_and_offset(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.longform.publication_documents(
            PUB_URI, tags=["essays", "tech"], count=50, offset=40))
        assert m.call_args.args[1] == f"/publications/{PUB_URI_ENC}/documents"
        assert m.call_args.kwargs["params"] == {
            "tags": ["essays", "tech"], "count": 50, "from": 40,
        }
        asyncio.run(c.close())

    def test_search_publications_and_search_namespace_helper(self):
        c, m, asyncio = self._async_client_and_mock()
        asyncio.run(c.longform.search_publications("climate", count=5, offset=10))
        assert m.call_args.args[1] == "/search/publications"
        assert m.call_args.kwargs["params"] == {"q": "climate", "count": 5, "from": 10}
        asyncio.run(c.search.publications("climate", count=5, offset=10))
        assert m.call_args.args[1] == "/search/publications"
        assert m.call_args.kwargs["params"] == {"q": "climate", "count": 5, "from": 10}
        asyncio.run(c.close())
