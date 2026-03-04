"""LimeSurvey RemoteControl 2 API client."""

import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from kobo2ddi.transform import extract_variables, parse_xlsform
from limesurvey2ddi.transform import _norm

load_dotenv()

DEFAULT_SERVER = "https://lime.correlaid.org"

# LimeSurvey adds these metadata columns to every export — not survey questions
_LIME_META_FIELDS = {
    "id", "submitdate", "startdate", "datestamp", "lastpage",
    "startlanguage", "seed", "ipaddr", "refurl", "token",
}


class LimeSurveyClient:
    """Client for the LimeSurvey RemoteControl 2 JSON-RPC API."""

    def __init__(
        self,
        server_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self._session_key: str | None = None
        self._rpc_id = 0
        self.server_url = (
            server_url or os.environ.get("LIME_SERVER_URL") or DEFAULT_SERVER
        ).rstrip("/")
        self._username = username or os.environ.get("LIME_USERNAME")
        self._password = password or os.environ.get("LIME_PASSWORD")
        if not self._username or not self._password:
            raise ValueError(
                "Username and password required. "
                "Set LIME_USERNAME and LIME_PASSWORD or pass them as arguments."
            )
        self._http = httpx.Client(timeout=60)

    # -- JSON-RPC transport --------------------------------------------------

    def _rpc(self, method: str, *params) -> object:
        """Make a single JSON-RPC 2.0 call.

        For all methods except get_session_key and release_session_key, the
        session key is automatically obtained (if needed) and prepended to params.
        """
        _auth_methods = ("get_session_key", "release_session_key")
        if method not in _auth_methods:
            if self._session_key is None:
                self._session_key = self._rpc(
                    "get_session_key", self._username, self._password
                )
            params = (self._session_key, *params)

        self._rpc_id += 1
        payload = {"method": method, "params": list(params), "id": self._rpc_id}
        resp = self._http.post(
            f"{self.server_url}/index.php/admin/remotecontrol",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"LimeSurvey API error in {method!r}: {data['error']}")
        return data["result"]

    def __del__(self):
        if self._session_key:
            try:
                self._rpc("release_session_key", self._session_key)
            except Exception:
                pass

    # -- surveys -------------------------------------------------------------

    def list_surveys(self) -> list[dict]:
        """Return all surveys accessible to the authenticated user."""
        result = self._rpc("list_surveys", self._username)
        if isinstance(result, dict) and result.get("status"):
            return []  # "No surveys found"
        return result

    # -- responses -----------------------------------------------------------

    def get_responses(self, survey_id: int) -> list[dict]:
        """Return all responses for a survey as a list of dicts keyed by question code."""
        result = self._rpc(
            "export_responses",
            survey_id,
            "json",
            None,       # language: use default
            "all",      # completion status
            "code",     # heading type: use question codes as keys
            "long",     # response type: full answer text
        )
        if isinstance(result, dict) and result.get("status"):
            return []   # no responses yet

        raw = base64.b64decode(result).decode("utf-8")
        data = json.loads(raw)
        rows = data.get("responses", [])
        responses = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            # LimeSurvey versions differ in response wrapping:
            # - Nested: {"1": {"id": 1, "field": value, ...}}
            # - Flat:   {"id": 1, "field": value, ...}
            first_val = next(iter(item.values()), None)
            if isinstance(first_val, dict):
                responses.append(first_val)   # unwrap nested
            else:
                responses.append(item)        # already flat
        return responses

    # -- validation ----------------------------------------------------------

    def validate(self, survey_id: int, output_dir: Path | None = None) -> bool:
        """Check that form.xlsx and responses.json correspond to the same survey.

        Compares variable names from the XLSForm against response column names,
        accounting for LimeSurvey metadata fields and select_multiple sub-columns
        (stored as varname[SQxxx]).

        Returns True if no undocumented response columns found, False otherwise.
        """
        out = (output_dir or Path("output")) / str(survey_id)
        form_path = out / "form.xlsx"
        responses_path = out / "responses.json"

        if not form_path.exists():
            print(f"  form.xlsx not found in {out} — place your XLSForm export there.")
            return False
        if not responses_path.exists():
            print(f"  responses.json not found in {out} — run pull first.")
            return False

        # Variable names from XLSForm
        survey_rows, choices_by_list, settings = parse_xlsform(form_path)
        variables = extract_variables(survey_rows, choices_by_list)
        form_names = {v["name"] for v in variables}

        # Column names from responses (first response's keys, minus metadata)
        responses = json.loads(responses_path.read_text())
        if not responses:
            print("  responses.json is empty — nothing to validate.")
            return True
        response_keys = set(responses[0].keys()) - _LIME_META_FIELDS

        # select_multiple variables appear as varname[SQxxx] in LimeSurvey exports
        # Reduce those to their base variable name for matching
        response_base_names: set[str] = set()
        subcolumn_map: dict[str, str] = {}  # subcolumn → base name
        for key in response_keys:
            if "[" in key:
                base = key.split("[")[0]
                subcolumn_map[key] = base
                response_base_names.add(base)
            else:
                response_base_names.add(key)

        # LimeSurvey strips underscores from question codes on export.
        # _norm() from limesurvey2ddi.transform normalises both sides for matching.
        norm_form = {_norm(n): n for n in form_names}
        norm_response = {_norm(n): n for n in response_base_names}

        matched_norm = set(norm_form) & set(norm_response)
        only_in_form = {norm_form[n] for n in set(norm_form) - matched_norm}
        only_in_responses = {norm_response[n] for n in set(norm_response) - matched_norm}

        print(f"  Matched:            {len(matched_norm)} variable(s)")
        if only_in_form:
            print(f"  In form only:       {len(only_in_form)} — {sorted(only_in_form)}")
        if only_in_responses:
            print(f"  In responses only:  {len(only_in_responses)} — {sorted(only_in_responses)}")
            print("  WARNING: undocumented response columns — form.xlsx may not match this survey.")
            return False

        print("  OK: all response columns are documented in form.xlsx")
        return True

    # -- convenience: pull ---------------------------------------------------

    def pull(self, survey_id: int, output_dir: Path | None = None) -> Path:
        """Download responses into *output_dir*/<survey_id>/responses.json.

        If form.xlsx is already present in the output directory, also validates
        that the form and responses correspond to the same survey.
        """
        out = (output_dir or Path("output")) / str(survey_id)
        out.mkdir(parents=True, exist_ok=True)

        responses = self.get_responses(survey_id)
        (out / "responses.json").write_text(
            json.dumps(responses, indent=2, ensure_ascii=False)
        )
        print(f"Saved {len(responses)} responses to {out / 'responses.json'}")

        form_path = out / "form.xlsx"
        if form_path.exists():
            print("Validating form.xlsx against responses:")
            ok = self.validate(survey_id, output_dir)
            if not ok:
                sys.exit(1)
        else:
            print(f"Place your XLSForm export as {form_path} for the transform step.")

        return out
