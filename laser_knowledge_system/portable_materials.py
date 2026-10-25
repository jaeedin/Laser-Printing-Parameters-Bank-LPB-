"""Portable material packages stored as folders beside the local database."""
from __future__ import annotations

import json
import re
import csv
from hashlib import sha1
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from laser_knowledge_system.db.repositories import RepositoryError, SQLiteRepository
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord


PACKAGE_FILENAME = "data.json"
DRAFTS_FILENAME = "open_records.json"
EXPERIMENT_DRAFTS_FILENAME = "open_experiments.json"
LEGACY_FIELD_ALIASES = {
    "conversion": ("conversion", "conversion_model", "model", "algorithm"),
    "direction": ("direction", "orientation"),
    "speed": ("speed", "speed_mm_min"),
    "power": ("power", "power_percent"),
    "quality": ("quality", "quality_lines_mm", "quality_percent"),
}


def _coalesce(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_profile_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return only material identity and the five supported print settings."""
    direction = _coalesce(data, *LEGACY_FIELD_ALIASES["direction"])
    if direction is None:
        legacy_preset = _coalesce(data, "preset", "variant_name")
        if str(legacy_preset).casefold() in {"horizontal", "vertical", "diagonal", "bidirectional"}:
            direction = legacy_preset
    normalized = {
        "material_name": str(data.get("material_name", "")).strip(),
        "conversion": _coalesce(data, *LEGACY_FIELD_ALIASES["conversion"]),
        "direction": direction,
        "speed": _coalesce(data, *LEGACY_FIELD_ALIASES["speed"]),
        "power": _coalesce(data, *LEGACY_FIELD_ALIASES["power"]),
        "quality": _coalesce(data, *LEGACY_FIELD_ALIASES["quality"]),
    }
    if data.get("id"):
        normalized["id"] = str(data["id"])
    if data.get("scope") in ("global", "user"):
        normalized["scope"] = data["scope"]
    return normalized


def validate_profile_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate the complete required print-setting record."""
    payload = normalize_profile_data(data)
    missing = [key for key in ("material_name", "conversion", "direction", "speed", "power", "quality") if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Missing material fields: {', '.join(missing)}.")
    try:
        payload["speed"] = float(payload["speed"])
        payload["power"] = float(payload["power"])
        payload["quality"] = float(payload["quality"])
    except (TypeError, ValueError) as error:
        raise ValueError("Speed, power, and quality must be numeric.") from error
    if payload["speed"] <= 0 or payload["quality"] <= 0 or payload["power"] < 0:
        raise ValueError("Speed and quality must be greater than zero; power cannot be negative.")
    for field in ("conversion", "direction"):
        payload[field] = str(payload[field]).strip()
        if not payload[field]:
            raise ValueError(f"{field.title()} cannot be empty.")
    return payload


@dataclass(frozen=True, slots=True)
class MaterialPackage:
    """The portable, user-facing metadata for one saved laser setting."""

    folder: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

def vault_path(root: Path | None = None) -> Path:
    """Return (and create) the material vault relative to the application data."""
    path = (root or Path.cwd()) / "materials_vault"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "material"


def _record_from_package(package: MaterialPackage) -> MaterialRecord:
    name = str(package.data["material_name"])
    return MaterialRecord(id=package.id, family=MaterialFamily.OTHER, name=name)


def profile_key(data: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    """The identity used for safe imports: exact variable duplicates are skipped."""
    normalized = validate_profile_data(data)
    return tuple(str(normalized.get(key, "")).strip().lower() for key in ("material_name", "conversion", "direction", "speed", "power", "quality"))


def profile_id(data: dict[str, Any]) -> str:
    normalized = validate_profile_data(data)
    seed = "|".join(str(normalized.get(key, "")) for key in ("material_name", "conversion", "direction", "speed", "power", "quality"))
    return f"{_slug(str(normalized['material_name']))}_{sha1(seed.encode()).hexdigest()[:12]}"


def write_package(vault: Path, data: dict[str, Any]) -> MaterialPackage:
    """Create a self-contained folder. Its JSON remains useful outside this app."""
    payload = validate_profile_data(data)
    payload.setdefault("id", profile_id(payload))
    folder = vault / _slug(str(payload["id"]))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / PACKAGE_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return MaterialPackage(folder, payload)


def scan_packages(vault: Path) -> list[MaterialPackage]:
    """Read valid packages. Invalid dropped folders are ignored rather than crashing startup."""
    packages: list[MaterialPackage] = []
    for source in vault.glob(f"*/{PACKAGE_FILENAME}"):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not all(key in payload for key in ("id", "material_name")):
                continue
            legacy = not all(key in payload for key in ("conversion", "direction", "speed", "power", "quality"))
            readable = dict(payload)
            if legacy:
                if _coalesce(readable, *LEGACY_FIELD_ALIASES["direction"]) is None:
                    preset = _coalesce(readable, "preset", "variant_name")
                    readable["direction"] = (
                        preset
                        if str(preset).casefold() in {"horizontal", "vertical", "diagonal", "bidirectional"}
                        else "Horizontal"
                    )
                if readable.get("quality") in (None, ""):
                    readable["quality"] = _coalesce(readable, "quality_lines_mm") or 15
            normalized = validate_profile_data(readable)
            normalized["id"] = str(payload["id"])
            normalized["scope"] = payload.get("scope") if payload.get("scope") in ("global", "user") else "global"
            packages.append(MaterialPackage(source.parent, normalized))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return sorted(packages, key=lambda package: str(package.data["material_name"]).lower())


def sync_vault(repo: SQLiteRepository, vault: Path) -> list[MaterialPackage]:
    """Index dropped packages in SQLite while retaining folders as the portable source."""
    packages = scan_packages(vault)
    for package in packages:
        if repo.get_material(package.id) is None:
            try:
                repo.add_material(_record_from_package(package))
            except (RepositoryError, ValueError):
                # A foreign package should never prevent the rest of the vault opening.
                continue
    return packages


def import_profiles(repo: SQLiteRepository, vault: Path, source: Path) -> tuple[int, int]:
    """Merge JSON or CSV into the vault without overwriting existing profile identities."""
    if source.suffix.lower() == ".csv":
        with source.open("r", newline="", encoding="utf-8-sig") as handle:
            incoming = list(csv.DictReader(handle))
    else:
        decoded = json.loads(source.read_text(encoding="utf-8"))
        incoming = decoded.get("profiles", decoded) if isinstance(decoded, dict) else decoded
    if not isinstance(incoming, list):
        raise ValueError("Import file must contain a JSON list/profiles list or a CSV header row.")
    known = {profile_key(package.data) for package in scan_packages(vault)}
    added = skipped = 0
    for item in incoming:
        if not isinstance(item, dict) or not item.get("material_name"):
            skipped += 1; continue
        key = profile_key(item)
        if key in known:
            skipped += 1; continue
        write_package(vault, item)
        known.add(key); added += 1
    sync_vault(repo, vault)
    return added, skipped


def load_open_record(root: Path) -> dict[str, Any] | None:
    source = root / DRAFTS_FILENAME
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_open_record(root: Path, data: dict[str, Any]) -> None:
    (root / DRAFTS_FILENAME).write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_open_record(root: Path) -> None:
    source = root / DRAFTS_FILENAME
    if source.exists():
        source.unlink()


def load_experiment_drafts(root: Path) -> list[dict[str, Any]]:
    """Return unfinished experiment batches, newest first.

    Experiment rows are intentionally stored outside SQLite: they survive an app
    restart even when a user has not yet chosen a winning preset.
    """
    source = root / EXPERIMENT_DRAFTS_FILENAME
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_experiment_draft(root: Path, draft: dict[str, Any]) -> None:
    """Upsert a named experiment batch without disturbing other open batches."""
    drafts = [item for item in load_experiment_drafts(root) if item.get("id") != draft.get("id")]
    drafts.insert(0, draft)
    (root / EXPERIMENT_DRAFTS_FILENAME).write_text(json.dumps(drafts, indent=2), encoding="utf-8")


def clear_experiment_draft(root: Path, draft_id: str) -> None:
    drafts = [item for item in load_experiment_drafts(root) if item.get("id") != draft_id]
    source = root / EXPERIMENT_DRAFTS_FILENAME
    if drafts:
        source.write_text(json.dumps(drafts, indent=2), encoding="utf-8")
    elif source.exists():
        source.unlink()


def update_package(package: MaterialPackage, data: dict[str, Any]) -> MaterialPackage:
    """Update one profile in place so its portable folder identity remains stable."""
    payload = validate_profile_data({**package.data, **data, "id": package.id})
    (package.folder / PACKAGE_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return MaterialPackage(package.folder, payload)


def delete_package(package: MaterialPackage) -> None:
    """Remove exactly one portable profile package after the UI confirmation."""
    shutil.rmtree(package.folder)


def find_profile(vault: Path, data: dict[str, Any]) -> MaterialPackage | None:
    """Find an exact duplicate across material and the five supported settings."""
    target = profile_key(data)
    for package in scan_packages(vault):
        if profile_key(package.data) == target:
            return package
    return None
