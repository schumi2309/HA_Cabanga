"""Config flow pour Cabanga."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CabangaApiClient, CabangaApiError, CabangaAuthError
from .const import CONF_REFRESH_TOKEN, CONF_STUDENTS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _parse_students(raw: str) -> list[dict]:
    """Parse 'ecole1:id1:Nom1, ecole2:id2:Nom2' -> [{"school_id": ..., "id": ..., "name": ...}, ...].

    Chaque élève porte son propre school_id, car des enfants d'une même
    famille peuvent être scolarisés dans des écoles différentes.
    """
    students = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 3:
            raise ValueError(f"Format invalide pour '{chunk}', attendu ecole:id:Nom")
        school_id, student_id, name = (p.strip() for p in parts)
        students.append({"school_id": school_id, "id": student_id, "name": name})
    if not students:
        raise ValueError("Aucun élève fourni")
    return students


class CabangaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère la configuration de l'intégration Cabanga."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                students = _parse_students(user_input[CONF_STUDENTS])
            except ValueError:
                errors[CONF_STUDENTS] = "invalid_students_format"
            else:
                session = async_get_clientsession(self.hass)
                client = CabangaApiClient(session, user_input[CONF_REFRESH_TOKEN])
                try:
                    # On valide que le refresh_token fonctionne réellement
                    await client.async_refresh_access_token()
                except CabangaAuthError:
                    errors["base"] = "invalid_refresh_token"
                except CabangaApiError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="Cabanga",
                        data={
                            CONF_REFRESH_TOKEN: client.refresh_token,
                            CONF_STUDENTS: students,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_REFRESH_TOKEN): str,
                vol.Required(CONF_STUDENTS): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "students_example": "ECOLE1:11111111:Prenom1, ECOLE2:22222222:Prenom2"
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.FlowResult:
        """Déclenché automatiquement par HA quand ConfigEntryAuthFailed est levée.

        L'utilisateur verra un bouton "Ré-authentifier" sur l'intégration
        dans Paramètres > Appareils et services, sans avoir à la supprimer.
        """
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Demande uniquement un nouveau refresh_token, garde le reste (élèves) intact."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = CabangaApiClient(session, user_input[CONF_REFRESH_TOKEN])
            try:
                await client.async_refresh_access_token()
            except CabangaAuthError:
                errors["base"] = "invalid_refresh_token"
            except CabangaApiError:
                errors["base"] = "cannot_connect"
            else:
                new_data = dict(self._reauth_entry.data)
                new_data[CONF_REFRESH_TOKEN] = client.refresh_token
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_REFRESH_TOKEN): str}),
            errors=errors,
        )
