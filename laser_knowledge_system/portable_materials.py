"""Portable material packages stored as folders beside the local database."""
from __future__ import annotations

import json
import re
import shutil
import csv
from hashlib import sha1
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from laser_knowledge_system.db.repositories import RepositoryError, SQLiteRepository
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord


PACKAGE_FILENAME = "data.json"
PREVIEW_FILENAME = "preview.png"
DRAFTS_FILENAME = "open_records.json"
EXPERIMENT_DRAFTS_FILENAME = "open_experiments.json"
LEGACY_FIELD_ALIASES = {
    "conversion": ("conversion", "conversion_model", "model", "algorithm"),
    "direction": ("direction", "preset", "variant_name", "orientation"),
    "speed": ("speed", "speed_mm_min", "speed_mm_s"),
    "power": ("power", "power_percent", "power_w"),
    "quality": ("quality", "quality_lines_mm", "quality_percent"),
}


def _coalesce(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_profile_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize new canonical fields while accepting legacy names for compatibility."""
    payload = dict(data)
    payload["material_name"] = str(payload.get("material_name", "")).strip()
    payload["conversion"] = str(_coalesce(payload, *LEGACY_FIELD_ALIASES["conversion"]) or "Pass-through")
    payload["direction"] = str(_coalesce(payload, *LEGACY_FIELD_ALIASES["direction"]) or "Horizontal")
    payload["speed"] = _coalesce(payload, *LEGACY_FIELD_ALIASES["speed"]) or 0
    payload["power"] = _coalesce(payload, *LEGACY_FIELD_ALIASES["power"]) or 0
    payload["quality"] = _coalesce(payload, *LEGACY_FIELD_ALIASES["quality"]) or 0
    for alias in ("conversion_model", "preset", "variant_name", "model", "algorithm", "speed_mm_min", "speed_mm_s", "power_percent", "power_w", "quality_lines_mm", "quality_percent", "blur", "brightness", "contrast", "torque", "dark_light"):
        payload.pop(alias, None)
    payload.pop("blur", None)
    payload.pop("brightness", None)
    payload.pop("contrast", None)
    payload.pop("torque", None)
    payload.pop("presets", None)
    payload.pop("dark_light", None)
    payload.pop("light_dark", None)
    return payload


@dataclass(frozen=True, slots=True)
class MaterialPackage:
    """The portable, user-facing metadata for one saved laser setting."""

    folder: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def preview_path(self) -> Path:
        return self.folder / str(self.data.get("image_filename", PREVIEW_FILENAME))


def vault_path(root: Path | None = None) -> Path:
    """Return (and create) the material vault relative to the application data."""
    path = (root or Path.cwd()) / "materials_vault"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "material"


def _family_for(name: str) -> MaterialFamily:
    text = name.lower()
    if any(word in text for word in ("wood", "plywood", "birch", "mdf", "bamboo")):
        return MaterialFamily.WOOD
    if any(word in text for word in ("acrylic", "plastic", "poly", "abs", "petg")):
        return MaterialFamily.PLASTIC
    if any(word in text for word in ("steel", "aluminium", "aluminum", "brass", "copper", "metal")):
        return MaterialFamily.METAL
    return MaterialFamily.OTHER


def _record_from_package(package: MaterialPackage) -> MaterialRecord:
    name = str(package.data["material_name"])
    family = _family_for(name)
    thickness = package.data.get("thickness_mm")
    if family is MaterialFamily.WOOD:
        properties: dict[str, Any] = {"species": name}
        if thickness is not None:
            properties["thickness_mm"] = float(thickness)
    elif family is MaterialFamily.PLASTIC:
        properties = {"material_type": name}
        if thickness is not None:
            properties["thickness_mm"] = float(thickness)
    elif family is MaterialFamily.METAL:
        properties = {"material_type": name}
        if thickness is not None:
            properties["thickness_mm"] = float(thickness)
    else:
        properties = {"material_type": name}
    return MaterialRecord(id=package.id, family=family, name=name, properties=properties, notes=str(package.data.get("notes", "")))


def profile_key(data: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """The identity used for safe imports: exact variable duplicates are skipped."""
    normalized = normalize_profile_data(data)
    return tuple(str(normalized.get(key, "")).strip().lower() for key in ("material_name", "conversion", "direction", "speed", "power"))


def profile_id(data: dict[str, Any]) -> str:
    normalized = normalize_profile_data(data)
    seed = "|".join(str(normalized.get(key, "")) for key in ("material_name", "conversion", "direction", "speed", "power", "quality"))
    return f"{_slug(str(normalized['material_name']))}_{sha1(seed.encode()).hexdigest()[:12]}"


def write_package(vault: Path, data: dict[str, Any], image_source: Path | None = None) -> MaterialPackage:
    """Create a self-contained folder. Its JSON remains useful outside this app."""
    normalized = normalize_profile_data(data)
    required = ("material_name", "conversion", "direction", "speed", "power", "quality")
    missing = [key for key in required if normalized.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Missing material fields: {', '.join(missing)}.")
    payload = dict(normalized)
    supplied_id = bool(payload.get("id"))
    payload.setdefault("id", profile_id(payload))
    payload.setdefault("thickness_mm", 0)
    payload.setdefault("operation", "Engrave")
    payload.setdefault("passes", 1)
    payload.setdefault("laser_wattage", "Unspecified")
    thickness_label = f"{float(payload['thickness_mm']):g}"
    base_folder = f"{_slug(str(payload['material_name']))}_{thickness_label}mm_{_slug(str(payload['operation']))}"
    folder = vault / (base_folder if supplied_id else f"{base_folder}_{_slug(str(payload['id']))}")
    folder.mkdir(parents=True, exist_ok=True)
    payload["image_filename"] = PREVIEW_FILENAME if image_source else payload.get("image_filename", "")
    if image_source:
        source = Path(image_source)
        if not source.is_file():
            raise ValueError("The selected preview image does not exist.")
        shutil.copy2(source, folder / PREVIEW_FILENAME)
    (folder / PACKAGE_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return MaterialPackage(folder, payload)


def scan_packages(vault: Path) -> list[MaterialPackage]:
    """Read valid packages. Invalid dropped folders are ignored rather than crashing startup."""
    packages: list[MaterialPackage] = []
    for source in vault.glob(f"*/{PACKAGE_FILENAME}"):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not all(key in payload for key in ("id", "material_name", "operation")):
                continue
            packages.append(MaterialPackage(source.parent, payload))
        except (OSError, json.JSONDecodeError):
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


def update_package(package: MaterialPackage, data: dict[str, Any], image_source: Path | None = None) -> MaterialPackage:
    """Update one profile in place so its portable folder identity remains stable."""
    payload = {**package.data, **data, "id": package.id}
    payload["image_filename"] = package.data.get("image_filename", "")
    if image_source:
        shutil.copy2(image_source, package.folder / PREVIEW_FILENAME)
        payload["image_filename"] = PREVIEW_FILENAME
    (package.folder / PACKAGE_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return MaterialPackage(package.folder, payload)


def delete_package(package: MaterialPackage) -> None:
    """Remove exactly one portable profile package after the UI confirmation."""
    shutil.rmtree(package.folder)


def find_profile(vault: Path, material_name: str, conversion_model: str, variant_name: str) -> MaterialPackage | None:
    """Locate the published preset identity used by the overwrite confirmation."""
    for package in scan_packages(vault):
        data = package.data
        if (str(data.get("material_name", "")).casefold(), str(data.get("conversion_model", "")).casefold(), str(data.get("variant_name", "Base")).casefold()) == (material_name.casefold(), conversion_model.casefold(), variant_name.casefold()):
            return package
    return None
