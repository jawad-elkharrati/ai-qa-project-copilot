from __future__ import annotations

import os

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
READ_TIMEOUT = 10.0
WRITE_TIMEOUT = 30.0


class DashboardAPIError(RuntimeError):
    def __init__(self, message: str, technical_detail: str = "") -> None:
        super().__init__(message)
        self.technical_detail = technical_detail


def _request(method: str, path: str, *, params=None, payload=None):
    try:
        if method == "GET":
            response = httpx.get(
                f"{API_URL}{path}",
                params=params,
                timeout=READ_TIMEOUT,
            )
        else:
            response = httpx.post(
                f"{API_URL}{path}",
                params=params,
                json=payload,
                timeout=WRITE_TIMEOUT,
            )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise DashboardAPIError(
            "L'API met trop de temps à répondre. Réessayez dans quelques instants.",
            str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise DashboardAPIError(
            f"L'API a refusé la requête (HTTP {status}).",
            str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise DashboardAPIError(
            "L'API QA est indisponible. Vérifiez que FastAPI est démarré.",
            str(exc),
        ) from exc
    except (TypeError, ValueError) as exc:
        raise DashboardAPIError(
            "La réponse de l'API n'est pas exploitable.",
            str(exc),
        ) from exc


def api_get(path: str, **params):
    return _request("GET", path, params=params or None)


def api_post(path: str, *, payload=None, **params):
    return _request("POST", path, params=params or None, payload=payload)
