"""KoboToolbox API v2 client."""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SERVER = "https://eu.kobotoolbox.org"


class KoboClient:
    """Simple client for the KoboToolbox API v2."""

    def __init__(self, token: str | None = None, server_url: str | None = None):
        self.server_url = (
            server_url or os.environ.get("KOBO_SERVER_URL") or DEFAULT_SERVER
        ).rstrip("/")
        token = token or os.environ.get("KOBO_API_TOKEN")
        if not token:
            raise ValueError(
                "API token required. Set KOBO_API_TOKEN or pass token= argument."
            )
        self._http = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Token {token}"},
            timeout=60,
        )

    # -- assets (surveys) ---------------------------------------------------

    def list_assets(self) -> list[dict]:
        """Return all assets (surveys/forms) the token has access to."""
        assets: list[dict] = []
        url = "/api/v2/assets/"
        while url:
            resp = self._http.get(url)
            resp.raise_for_status()
            data = resp.json()
            assets.extend(data["results"])
            url = data.get("next")
        return assets

    def get_asset(self, uid: str) -> dict:
        """Return full asset detail including form content."""
        resp = self._http.get(f"/api/v2/assets/{uid}/")
        resp.raise_for_status()
        return resp.json()

    # -- submissions --------------------------------------------------------

    def get_submissions(self, uid: str) -> list[dict]:
        """Return all submissions for an asset, handling pagination."""
        submissions: list[dict] = []
        url = f"/api/v2/assets/{uid}/data/?format=json"
        while url:
            resp = self._http.get(url)
            resp.raise_for_status()
            data = resp.json()
            submissions.extend(data["results"])
            url = data.get("next")
        return submissions

    # -- xlsform download ---------------------------------------------------

    def download_xlsform(self, uid: str, dest: Path) -> Path:
        """Download the XLSForm for an asset to *dest*.

        Kobo serves xlsx content from the ``.xls`` endpoint, so we save
        with a ``.xlsx`` extension for compatibility with openpyxl.
        """
        resp = self._http.get(f"/api/v2/assets/{uid}.xls")
        resp.raise_for_status()
        # Force .xlsx extension — the API returns xlsx despite the .xls URL
        dest = dest.with_suffix(".xlsx")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest

    # -- convenience: pull everything ---------------------------------------

    def pull(self, uid: str, output_dir: Path | None = None) -> Path:
        """Download submissions + XLSForm into *output_dir*/<uid>/."""
        out = (output_dir or Path("output")) / uid
        out.mkdir(parents=True, exist_ok=True)

        submissions = self.get_submissions(uid)
        (out / "submissions.json").write_text(
            json.dumps(submissions, indent=2, ensure_ascii=False)
        )

        self.download_xlsform(uid, out / "form.xlsx")

        print(f"Saved {len(submissions)} submissions and form.xlsx to {out}")
        return out
