import json
import os

from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def _auth_headers():
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not service_key:
        raise RuntimeError("Supabase server credentials are not configured.")

    headers = {
        "apikey": service_key,
    }

    if not service_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service_key}"

    return headers


def _request(method, table, payload, query=None):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        raise RuntimeError("Supabase server credentials are not configured.")

    url = f"{supabase_url}/rest/v1/{quote(table, safe='')}"
    if query:
        url = f"{url}?{query}"

    headers = {
        **_auth_headers(),
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    body = None
    if payload is not None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"Supabase returned HTTP {error.code}."
        ) from None

    if not response_body:
        return []

    return json.loads(response_body.decode("utf-8"))


def _storage_request(method, object_path, payload=None, content_type=None):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    bucket = os.environ.get(
        "SUPABASE_HISTORY_BUCKET",
        "stego-history"
    )

    if not supabase_url:
        raise RuntimeError("Supabase URL is not configured.")

    url = (
        f"{supabase_url}/storage/v1/object/"
        f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
    )
    headers = _auth_headers()

    if content_type:
        headers["Content-Type"] = content_type

    if method == "POST":
        headers["x-upsert"] = "true"

    request = Request(
        url,
        data=payload,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=20) as response:
            return response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"Supabase Storage returned HTTP {error.code}."
        ) from None


def upload_history_image(object_path, image_bytes):
    _storage_request(
        "POST",
        object_path,
        image_bytes,
        "image/png"
    )


def download_history_image(object_path):
    return _storage_request(
        "GET",
        object_path
    )


def delete_history_image(object_path):
    _storage_request(
        "DELETE",
        object_path
    )


def insert_row(table, values):
    rows = _request("POST", table, values)
    if not rows:
        raise RuntimeError("Supabase did not return the inserted row.")
    return rows[0]


def insert_rows(table, values):
    if values:
        _request("POST", table, values)


def list_recent_runs(limit=50):
    query = urlencode({
        "select": "*,bit_mode_results(*)",
        "order": "created_at.desc",
        "limit": max(1, min(int(limit), 100)),
    })

    return _request(
        "GET",
        "steganography_runs",
        None,
        query
    )