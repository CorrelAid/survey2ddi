"""Tests for kobo2ddi.client — KoboClient with mocked HTTP."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest

from kobo2ddi.client import KoboClient


@pytest.fixture
def client():
    """Create a KoboClient with a fake token (HTTP calls will be mocked)."""
    return KoboClient(token="fake-token", server_url="https://example.org")


def _mock_response(json_data=None, content=b"", status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


class TestKoboClientInit:
    def test_requires_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API token required"):
                KoboClient()

    def test_token_from_argument(self):
        c = KoboClient(token="test-tok")
        assert c._http.headers["Authorization"] == "Token test-tok"

    def test_server_url_default(self):
        c = KoboClient(token="test-tok")
        assert "eu.kobotoolbox.org" in c.server_url

    def test_server_url_override(self):
        c = KoboClient(token="t", server_url="https://custom.org/")
        assert c.server_url == "https://custom.org"  # trailing slash stripped


class TestListAssets:
    def test_single_page(self, client):
        mock_resp = _mock_response(json_data={
            "results": [{"uid": "abc", "name": "Survey 1"}],
            "next": None,
        })
        with patch.object(client._http, "get", return_value=mock_resp) as mock_get:
            assets = client.list_assets()
            assert len(assets) == 1
            assert assets[0]["uid"] == "abc"
            mock_get.assert_called_once_with("/api/v2/assets/")

    def test_pagination(self, client):
        page1 = _mock_response(json_data={
            "results": [{"uid": "a1"}],
            "next": "/api/v2/assets/?page=2",
        })
        page2 = _mock_response(json_data={
            "results": [{"uid": "a2"}],
            "next": None,
        })
        with patch.object(client._http, "get", side_effect=[page1, page2]):
            assets = client.list_assets()
            assert len(assets) == 2
            assert assets[0]["uid"] == "a1"
            assert assets[1]["uid"] == "a2"


class TestGetAsset:
    def test_returns_asset_detail(self, client):
        mock_resp = _mock_response(json_data={"uid": "xyz", "name": "My Form"})
        with patch.object(client._http, "get", return_value=mock_resp):
            asset = client.get_asset("xyz")
            assert asset["name"] == "My Form"


class TestGetSubmissions:
    def test_returns_submissions(self, client):
        mock_resp = _mock_response(json_data={
            "results": [{"_id": 1, "q1": "yes"}, {"_id": 2, "q1": "no"}],
            "next": None,
        })
        with patch.object(client._http, "get", return_value=mock_resp):
            subs = client.get_submissions("uid1")
            assert len(subs) == 2

    def test_pagination(self, client):
        p1 = _mock_response(json_data={"results": [{"_id": 1}], "next": "/page2"})
        p2 = _mock_response(json_data={"results": [{"_id": 2}], "next": None})
        with patch.object(client._http, "get", side_effect=[p1, p2]):
            subs = client.get_submissions("uid1")
            assert len(subs) == 2


class TestDownloadXlsform:
    def test_saves_file_as_xlsx(self, client, tmp_path):
        mock_resp = _mock_response(content=b"fake-xlsx-content")
        with patch.object(client._http, "get", return_value=mock_resp):
            result = client.download_xlsform("uid1", tmp_path / "form.xls")
            assert result.suffix == ".xlsx"
            assert result.read_bytes() == b"fake-xlsx-content"


class TestPull:
    def test_creates_output_files(self, client, tmp_path):
        sub_resp = _mock_response(json_data={
            "results": [{"_id": 1, "q1": "a"}],
            "next": None,
        })
        xls_resp = _mock_response(content=b"fake-xls")
        with patch.object(client._http, "get", side_effect=[sub_resp, xls_resp]):
            out = client.pull("uid1", output_dir=tmp_path)
            assert (out / "submissions.json").exists()
            assert (out / "form.xlsx").exists()
            subs = json.loads((out / "submissions.json").read_text())
            assert len(subs) == 1
