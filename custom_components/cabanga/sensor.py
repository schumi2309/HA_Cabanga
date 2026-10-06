"""Capteurs Cabanga : journal de classe, devoirs à faire, dernière évaluation, absences, retours anticipés, agenda, remarques, arrivées tardives."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CabangaCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: CabangaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for student in coordinator.students:
        student_id = student["id"]
        entities.append(CabangaJournalSensor(coordinator, entry, student_id))
        entities.append(CabangaHomeworkSensor(coordinator, entry, student_id))
        entities.append(CabangaEvaluationSensor(coordinator, entry, student_id))
        entities.append(CabangaAbsenceSensor(coordinator, entry, student_id))
        entities.append(CabangaEarlyDepartureSensor(coordinator, entry, student_id))
        entities.append(CabangaAgendaSensor(coordinator, entry, student_id))
        entities.append(CabangaRemarkSensor(coordinator, entry, student_id))
        entities.append(CabangaLateArrivalSensor(coordinator, entry, student_id))

    async_add_entities(entities)


class _CabangaBaseSensor(CoordinatorEntity[CabangaCoordinator], SensorEntity):
    """Base commune : device par enfant + nom lisible."""

    def __init__(self, coordinator: CabangaCoordinator, entry: ConfigEntry, student_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._student_id = student_id

    @property
    def _student_data(self) -> dict:
        return self.coordinator.data.get(self._student_id, {})

    @property
    def _student_name(self) -> str:
        return self._student_data.get("name", self._student_id)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._student_id)},
            name=f"Cabanga - {self._student_name}",
            manufacturer="Scolares",
            model="Cabanga",
        )


class CabangaJournalSensor(_CabangaBaseSensor):
    """Cours/activités du jour pour l'enfant."""

    _attr_icon = "mdi:notebook-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_journal"
        self._attr_name = f"Journal de classe {self._student_name_init(coordinator, student_id)}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def native_value(self) -> int:
        return len(self._today_entries())

    @property
    def extra_state_attributes(self) -> dict:
        entries = self._today_entries()
        return {
            "cours": [
                {
                    "heure": e.get("hour"),
                    "matiere": e.get("lessonName"),
                    "sujet": e.get("lessonSubject"),
                }
                for e in sorted(entries, key=lambda e: e.get("hour") or "")
            ]
        }

    def _today_entries(self) -> list[dict]:
        today_str = date.today().isoformat()
        diary = self._student_data.get("diary", [])
        return [e for e in diary if e.get("date") == today_str]


class CabangaHomeworkSensor(_CabangaBaseSensor):
    """Nombre de devoirs non faits à venir."""

    _attr_icon = "mdi:notebook-check-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_devoirs"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Devoirs à faire {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def native_value(self) -> int:
        return len(self._pending_homework())

    @property
    def extra_state_attributes(self) -> dict:
        pending = sorted(self._pending_homework(), key=lambda e: e.get("date") or "")
        return {
            "devoirs": [
                {
                    "date": e.get("date"),
                    "matiere": e.get("lessonName"),
                    "consigne": e.get("homework"),
                }
                for e in pending
            ]
        }

    def _pending_homework(self) -> list[dict]:
        diary = self._student_data.get("diary", [])
        return [
            e for e in diary if e.get("homework") and e.get("homeworkDone") is False
        ]


class CabangaEvaluationSensor(_CabangaBaseSensor):
    """Dernière évaluation (note) reçue."""

    _attr_icon = "mdi:school-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_derniere_evaluation"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Dernière évaluation {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def _sorted_evaluations(self) -> list[dict]:
        evaluations = self._student_data.get("evaluations", [])
        return sorted(
            evaluations, key=lambda e: e.get("date") or "", reverse=True
        )

    @property
    def native_value(self) -> float | None:
        evals = self._sorted_evaluations
        if not evals:
            return None
        latest = evals[0]
        score = latest.get("score")
        try:
            return float(score)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        evals = self._sorted_evaluations
        if not evals:
            return {}
        latest = evals[0]
        return {
            "matiere": latest.get("subject"),
            "titre": latest.get("title"),
            "date": latest.get("date"),
            "score_max": latest.get("maximumScore"),
            "formative": latest.get("formative"),
            "5_dernieres": [
                {
                    "date": e.get("date"),
                    "matiere": e.get("subject"),
                    "titre": e.get("title"),
                    "score": e.get("score"),
                    "score_max": e.get("maximumScore"),
                }
                for e in evals[:5]
            ],
            "toutes": [
                {
                    "date": e.get("date"),
                    "matiere": e.get("subject"),
                    "titre": e.get("title"),
                    "score": e.get("score"),
                    "score_max": e.get("maximumScore"),
                    "formative": e.get("formative"),
                }
                for e in evals
            ],
        }


class CabangaAbsenceSensor(_CabangaBaseSensor):
    """Absences légales — structure JSON non confirmée (jamais observée avec
    des données réelles, aucun élève testé n'avait d'absence enregistrée).

    Le capteur reste volontairement générique : le nombre brut d'entrées
    comme état, et la liste brute telle que renvoyée par l'API en attribut.
    Dès qu'une vraie absence est enregistrée, la structure exacte pourra
    être observée et ce capteur affiné en conséquence.
    """

    _attr_icon = "mdi:account-alert-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_absences"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Absences {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def native_value(self) -> int:
        return len(self._student_data.get("absences", []))

    @property
    def extra_state_attributes(self) -> dict:
        absences = self._student_data.get("absences", [])
        return {"absences_brutes": absences}


class CabangaEarlyDepartureSensor(_CabangaBaseSensor):
    """Retours anticipés (sorties avant l'heure) sur l'année scolaire en cours."""

    _attr_icon = "mdi:exit-run"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_retours_anticipes"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Retours anticipés {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def _sorted_departures(self) -> list[dict]:
        departures = self._student_data.get("early_departures", [])
        return sorted(departures, key=lambda d: d.get("date") or "", reverse=True)

    @property
    def native_value(self) -> int:
        return len(self._sorted_departures)

    @property
    def extra_state_attributes(self) -> dict:
        departures = self._sorted_departures
        return {
            "retours": [
                {
                    "date": d.get("date"),
                    "heure": d.get("hour"),
                    "motif": d.get("reason"),
                    "classe": d.get("className"),
                    "autorise_par": f"{d.get('authorFirstName', '')} {d.get('authorLastName', '')}".strip(),
                }
                for d in departures
            ]
        }


class CabangaAgendaSensor(_CabangaBaseSensor):
    """Agenda/calendrier scolaire officiel (rentrées, bulletins, congés
    pédagogiques, réunions...). Au niveau école, identique pour tous les
    élèves d'une même école.
    """

    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_agenda"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Agenda {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def _upcoming_events(self) -> list[dict]:
        today_str = date.today().isoformat()
        agenda = self._student_data.get("agenda", [])
        upcoming = [e for e in agenda if (e.get("date") or "") >= today_str]
        return sorted(upcoming, key=lambda e: e.get("date") or "")

    @property
    def native_value(self) -> int:
        return len(self._upcoming_events)

    @property
    def _all_events_sorted(self) -> list[dict]:
        agenda = self._student_data.get("agenda", [])
        return sorted(agenda, key=lambda e: e.get("date") or "")

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self._upcoming_events
        return {
            "prochain_evenement": upcoming[0].get("activity") if upcoming else None,
            "prochaine_date": upcoming[0].get("date") if upcoming else None,
            "evenements": [
                {
                    "date": e.get("date"),
                    "activite": e.get("activity"),
                }
                for e in upcoming[:15]
            ],
            "tous_evenements": [
                {
                    "date": e.get("date"),
                    "activite": e.get("activity"),
                }
                for e in self._all_events_sorted
            ],
        }


class CabangaRemarkSensor(_CabangaBaseSensor):
    """Remarques (notes dans le journal de classe) sur l'année scolaire en cours."""

    _attr_icon = "mdi:message-alert-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_remarques"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Remarques {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def _sorted_remarks(self) -> list[dict]:
        remarks = self._student_data.get("remarks", [])
        return sorted(
            remarks,
            key=lambda r: f"{r.get('date') or ''} {r.get('hour') or ''}",
            reverse=True,
        )

    @property
    def native_value(self) -> int:
        return len(self._sorted_remarks)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "remarques": [
                {
                    "date": r.get("date"),
                    "heure": r.get("hour"),
                    "texte": r.get("text"),
                    "type": r.get("type"),
                    "auteur": f"{r.get('authorFirstName', '')} {r.get('authorLastName', '')}".strip(),
                    "classe": r.get("className"),
                    "vue_par_parents": bool(
                        r.get("viewedByFirstParent") or r.get("viewedBySecondParent")
                    ),
                }
                for r in self._sorted_remarks
            ]
        }


class CabangaLateArrivalSensor(_CabangaBaseSensor):
    """Arrivées tardives — BÊTA : structure JSON non confirmée (aucune donnée
    réelle observée). Nombre d'entrées comme état, liste brute en attribut ;
    sera affiné dès qu'un exemple réel sera disponible.
    """

    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator, entry, student_id) -> None:
        super().__init__(coordinator, entry, student_id)
        self._attr_unique_id = f"{DOMAIN}_{student_id}_arrivees_tardives"
        name = self._student_name_init(coordinator, student_id)
        self._attr_name = f"Arrivées tardives {name}"

    @staticmethod
    def _student_name_init(coordinator, student_id) -> str:
        return coordinator.data.get(student_id, {}).get("name", student_id) if coordinator.data else student_id

    @property
    def native_value(self) -> int:
        return len(self._student_data.get("late_arrivals", []))

    @property
    def extra_state_attributes(self) -> dict:
        return {"arrivees_brutes": self._student_data.get("late_arrivals", [])}
