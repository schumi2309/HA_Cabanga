"""Client API pour Cabanga (login.scolares.be / api.scolares.be)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import aiohttp

from .const import API_BASE_URL, CLIENT_ID, TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class CabangaAuthError(Exception):
    """Levée quand le refresh token est invalide/expiré (nécessite une reconnexion manuelle)."""


class CabangaApiError(Exception):
    """Levée pour toute autre erreur API."""


class CabangaApiClient:
    """Petit wrapper autour de l'API Cabanga.

    L'authentification se fait exclusivement via refresh_token (obtenu
    manuellement une première fois, cf. README) car le login initial est
    protégé par un Cloudflare Turnstile impossible à automatiser.
    """

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._access_token: str | None = None

    @property
    def refresh_token(self) -> str:
        """Retourne le refresh_token courant (peut changer à chaque refresh)."""
        return self._refresh_token

    async def async_refresh_access_token(self) -> None:
        """Échange le refresh_token contre un nouvel access_token.

        Keycloak fait tourner (rotate) le refresh_token à chaque appel : on
        garde donc systématiquement le nouveau pour le prochain cycle.
        """
        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": self._refresh_token,
        }
        async with self._session.post(TOKEN_URL, data=data) as resp:
            if resp.status == 400 or resp.status == 401:
                raise CabangaAuthError(
                    f"Refresh token rejeté (status {resp.status}) — "
                    "il faut probablement en capturer un nouveau manuellement."
                )
            if resp.status != 200:
                text = await resp.text()
                raise CabangaApiError(f"Erreur token refresh ({resp.status}): {text}")
            payload = await resp.json()

        self._access_token = payload["access_token"]
        # Le refresh_token change à chaque rotation : on met à jour la référence
        # locale. C'est à l'appelant (coordinator) de le repersister dans HA.
        self._refresh_token = payload.get("refresh_token", self._refresh_token)

    async def _authed_get(self, url: str, params: dict | None = None) -> Any:
        if self._access_token is None:
            await self.async_refresh_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with self._session.get(url, headers=headers, params=params) as resp:
            if resp.status == 401:
                # Access token expiré en cours de route -> on retente une fois
                await self.async_refresh_access_token()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                async with self._session.get(url, headers=headers, params=params) as retry_resp:
                    if retry_resp.status != 200:
                        text = await retry_resp.text()
                        raise CabangaApiError(f"Erreur API ({retry_resp.status}): {text}")
                    return await retry_resp.json()
            if resp.status != 200:
                text = await resp.text()
                raise CabangaApiError(f"Erreur API ({resp.status}): {text}")
            return await resp.json()

    async def async_get_diary(
        self, school_id: str, student_id: str, date_from: date, date_to: date
    ) -> list[dict]:
        """Journal de classe + devoirs pour un élève sur une plage de dates."""
        url = f"{API_BASE_URL}/schools/{school_id}/students/{student_id}/diary"
        params = {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        }
        return await self._authed_get(url, params)

    async def async_get_evaluations(
        self, school_id: str, student_id: str, year: int
    ) -> list[dict]:
        """Évaluations (notes) pour un élève sur une année scolaire donnée."""
        url = f"{API_BASE_URL}/schools/{school_id}/students/{student_id}/evaluations"
        params = {"year": year}
        return await self._authed_get(url, params)

    async def async_get_absences(self, school_id: str, student_id: str) -> list[dict]:
        """Absences légales pour un élève.

        Structure JSON non confirmée à ce jour (jamais observée avec des
        données réelles) : aucun élève testé n'avait d'absence enregistrée.
        L'appelant doit traiter le résultat de façon générique.
        """
        url = f"{API_BASE_URL}/schools/{school_id}/students/{student_id}/legalAbsences"
        return await self._authed_get(url)

    async def async_get_early_departures(
        self, school_id: str, student_id: str, year: int
    ) -> list[dict]:
        """Retours anticipés (sorties avant l'heure) pour un élève."""
        url = f"{API_BASE_URL}/schools/{school_id}/students/{student_id}/earlyDepartures"
        params = {"year": year}
        return await self._authed_get(url, params)

    async def async_get_agenda(self, school_id: str) -> list[dict]:
        """Agenda/calendrier scolaire officiel (au niveau école, pas par élève).

        Renvoie l'année complète en un seul appel (pas de pagination/dates
        en paramètre observée) : rentrées, bulletins, conseils de classe,
        réunions de parents, congés pédagogiques, etc.
        """
        url = f"{API_BASE_URL}/schools/{school_id}/agenda/activities"
        return await self._authed_get(url)
