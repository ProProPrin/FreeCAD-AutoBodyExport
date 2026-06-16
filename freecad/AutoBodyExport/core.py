"""Export selected FreeCAD objects after a document is saved."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import string
import uuid
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import FreeCAD as App

from .i18n import tr

DEFAULT_PARAMETER_PATH = "User parameter:BaseApp/Preferences/Mod/AutoBodyExport"
DOCUMENT_STATES_KEY = "DocumentStates"
ENABLED_KEY = "Enabled"
EXPORT_STEP_KEY = "ExportSTEP"
EXPORT_STL_KEY = "ExportSTL"
SHOW_DIALOG_KEY = "ShowDialog"
OUTPUT_MODE_KEY = "OutputMode"
CUSTOM_OUTPUT_DIRECTORY_KEY = "CustomOutputDirectory"
FILENAME_TEMPLATE_KEY = "FilenameTemplate"
HISTORY_LIMIT_KEY = "HistoryLimit"
STL_USE_FREECAD_SETTINGS_KEY = "STLUseFreeCADSettings"
STL_LINEAR_DEFLECTION_KEY = "STLLinearDeflection"
STL_ANGULAR_DEFLECTION_KEY = "STLAngularDeflection"
SHOW_PROGRESS_KEY = "ShowProgress"
SKIP_UNCHANGED_KEY = "SkipUnchanged"
SAVE_PROCESS_DELAY_MS = 50
DEFAULT_FILENAME_TEMPLATE = "{document}_{part}_{target}"
MAX_FILENAME_STEM_LENGTH = 180
DOCUMENT_DIRECTORY_FIELD = "document_dir"
DOCUMENT_PARENT_DIRECTORY_FIELD = "document_parent_dir"
DOCUMENT_DIRECTORY_TOKEN = "{" + DOCUMENT_DIRECTORY_FIELD + "}"
DOCUMENT_PARENT_DIRECTORY_TOKEN = "{" + DOCUMENT_PARENT_DIRECTORY_FIELD + "}"
OUTPUT_MODE_DOCUMENT = "document"
OUTPUT_MODE_CUSTOM = "custom"
OUTPUT_MODE_INHERIT = "inherit"
DOCUMENT_OUTPUT_MODES = {OUTPUT_MODE_INHERIT, OUTPUT_MODE_DOCUMENT, OUTPUT_MODE_CUSTOM}
FREECAD_MESH_PARAMETER_PATH = "User parameter:BaseApp/Preferences/Mod/Mesh"
FREECAD_MESH_MAX_DEVIATION_EXPORT_KEY = "MaxDeviationExport"
DEFAULT_STL_LINEAR_DEFLECTION = 0.1
DEFAULT_STL_ANGULAR_DEFLECTION = 0.5
GROUP_COLORS = (
    "#b8daf7",
    "#bfe8c8",
    "#dfc4f2",
    "#f6d2a6",
    "#bce4df",
    "#efc5d3",
)

PART_PREFIX = "part:"
BODY_PREFIX = "body:"
OBJECT_PREFIX = "object:"
GROUP_PREFIX = "group:"
UNPARENTED_GROUP_ID = "__unparented__"

INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
FILENAME_TEMPLATE_FIELDS = {"document", "part", "target", "name"}
OUTPUT_DIRECTORY_TEMPLATE_FIELDS = {
    DOCUMENT_DIRECTORY_FIELD,
    DOCUMENT_PARENT_DIRECTORY_FIELD,
}


@dataclass(frozen=True)
class PartInfo:
    object_name: str
    label: str
    parent_part_id: Optional[str]

    @property
    def item_id(self) -> str:
        return PART_PREFIX + self.object_name


@dataclass(frozen=True)
class BodyInfo:
    object_name: str
    label: str
    parent_part_id: Optional[str]

    @property
    def item_id(self) -> str:
        return BODY_PREFIX + self.object_name


@dataclass(frozen=True)
class ObjectInfo:
    object_name: str
    label: str
    type_id: str
    parent_part_id: str

    @property
    def item_id(self) -> str:
        return OBJECT_PREFIX + self.object_name


@dataclass(frozen=True)
class Inventory:
    parts: Tuple[PartInfo, ...]
    bodies: Tuple[BodyInfo, ...]
    objects: Tuple[ObjectInfo, ...] = ()

    @property
    def item_ids(self) -> Set[str]:
        return {part.item_id for part in self.parts} | self.individual_target_ids

    @property
    def body_ids(self) -> Set[str]:
        return {body.item_id for body in self.bodies}

    @property
    def object_ids(self) -> Set[str]:
        return {obj.item_id for obj in self.objects}

    @property
    def individual_target_ids(self) -> Set[str]:
        return self.body_ids | self.object_ids

    @property
    def target_infos(self) -> Tuple[object, ...]:
        return (*self.bodies, *self.objects)


@dataclass
class DocumentState:
    path: str
    known_item_ids: Set[str]
    selected_target_ids: Set[str]
    target_groups: List[Set[str]] = field(default_factory=list)
    enabled: bool = True
    generated_files: Set[str] = field(default_factory=set)
    export_signatures: Dict[str, str] = field(default_factory=dict)
    managed_output_roots: Set[str] = field(default_factory=set)
    output_mode: str = OUTPUT_MODE_INHERIT
    custom_output_directory: str = ""

    def to_json_value(self) -> dict:
        return {
            "path": self.path,
            "known_item_ids": sorted(self.known_item_ids),
            "selected_target_ids": sorted(self.selected_target_ids),
            "target_groups": [
                sorted(group)
                for group in sorted(
                    self.target_groups,
                    key=lambda value: tuple(sorted(value)),
                )
            ],
            "enabled": self.enabled,
            "generated_files": sorted(self.generated_files),
            "export_signatures": dict(sorted(self.export_signatures.items())),
            "managed_output_roots": sorted(self.managed_output_roots),
            "output_mode": self.output_mode,
            "custom_output_directory": self.custom_output_directory,
        }

    @classmethod
    def from_json_value(cls, value: object) -> Optional["DocumentState"]:
        if not isinstance(value, dict):
            return None
        path = value.get("path")
        known_item_ids = value.get("known_item_ids")
        selected_target_ids = value.get("selected_target_ids", value.get("selected_body_ids"))
        target_groups = value.get("target_groups", [])
        enabled = value.get("enabled", True)
        generated_files = value.get("generated_files", [])
        export_signatures = value.get("export_signatures", {})
        managed_output_roots = value.get("managed_output_roots", [])
        output_mode = value.get("output_mode", OUTPUT_MODE_INHERIT)
        custom_output_directory = value.get("custom_output_directory", "")
        if not isinstance(path, str):
            return None
        if not isinstance(known_item_ids, list) or not isinstance(selected_target_ids, list):
            return None
        if not isinstance(target_groups, list):
            target_groups = []
        if not isinstance(enabled, bool):
            enabled = True
        if not isinstance(generated_files, list):
            generated_files = []
        if not isinstance(export_signatures, dict):
            export_signatures = {}
        if not isinstance(managed_output_roots, list):
            managed_output_roots = []
        if output_mode not in DOCUMENT_OUTPUT_MODES:
            output_mode = OUTPUT_MODE_INHERIT
        if not isinstance(custom_output_directory, str):
            custom_output_directory = ""
        return cls(
            path=path,
            known_item_ids={item for item in known_item_ids if isinstance(item, str)},
            selected_target_ids={item for item in selected_target_ids if isinstance(item, str)},
            target_groups=[
                {item for item in group if isinstance(item, str)}
                for group in target_groups
                if isinstance(group, list)
            ],
            enabled=enabled,
            generated_files={
                normalize_document_path(item) for item in generated_files if isinstance(item, str)
            },
            export_signatures={
                normalize_document_path(path): signature
                for path, signature in export_signatures.items()
                if isinstance(path, str) and isinstance(signature, str)
            },
            managed_output_roots={
                normalize_document_path(path)
                for path in managed_output_roots
                if isinstance(path, str)
            },
            output_mode=output_mode,
            custom_output_directory=custom_output_directory,
        )


@dataclass(frozen=True)
class ExportOptions:
    export_step: bool
    export_stl: bool
    show_dialog: bool
    enabled: bool = False
    output_mode: str = OUTPUT_MODE_DOCUMENT
    custom_output_directory: str = ""
    filename_template: str = DEFAULT_FILENAME_TEMPLATE
    history_limit: int = 20
    stl_linear_deflection: float = DEFAULT_STL_LINEAR_DEFLECTION
    stl_angular_deflection: float = DEFAULT_STL_ANGULAR_DEFLECTION
    show_progress: bool = True
    skip_unchanged: bool = True
    stl_use_freecad_settings: bool = True


@dataclass(frozen=True)
class STLMeshSettings:
    source: str
    linear_deflection: float
    angular_deflection: float


@dataclass(frozen=True)
class DialogResult:
    accepted: bool
    selected_target_ids: Set[str]
    target_groups: List[Set[str]]
    export_step: bool
    export_stl: bool
    show_dialog: bool
    document_enabled: bool
    output_mode: str
    custom_output_directory: str


@dataclass
class ExportTargetPlan:
    target_ids: Tuple[str, ...]
    source_infos: Tuple[object, ...]
    source_objects: Tuple[object, ...]
    display_label: str
    stem: str
    signature_base: str


@dataclass
class ExportRunResult:
    failures: List[str] = field(default_factory=list)
    generated_files: Set[str] = field(default_factory=set)
    export_signatures: Dict[str, str] = field(default_factory=dict)
    managed_output_roots: Set[str] = field(default_factory=set)
    canceled: bool = False


def preferences():
    parameter_path = os.environ.get("AUTOBODYEXPORT_PARAMETER_PATH", DEFAULT_PARAMETER_PATH)
    return App.ParamGet(parameter_path)


def load_export_options() -> ExportOptions:
    params = preferences()
    output_mode = params.GetString(OUTPUT_MODE_KEY, OUTPUT_MODE_DOCUMENT)
    if output_mode not in (OUTPUT_MODE_DOCUMENT, OUTPUT_MODE_CUSTOM):
        output_mode = OUTPUT_MODE_DOCUMENT
    filename_template = params.GetString(FILENAME_TEMPLATE_KEY, DEFAULT_FILENAME_TEMPLATE)
    if not validate_filename_template(filename_template):
        filename_template = DEFAULT_FILENAME_TEMPLATE
    return ExportOptions(
        export_step=params.GetBool(EXPORT_STEP_KEY, True),
        export_stl=params.GetBool(EXPORT_STL_KEY, False),
        show_dialog=params.GetBool(SHOW_DIALOG_KEY, True),
        enabled=params.GetBool(ENABLED_KEY, False),
        output_mode=output_mode,
        custom_output_directory=params.GetString(CUSTOM_OUTPUT_DIRECTORY_KEY, ""),
        filename_template=filename_template,
        history_limit=max(0, params.GetInt(HISTORY_LIMIT_KEY, 20)),
        stl_linear_deflection=max(
            0.001,
            params.GetFloat(STL_LINEAR_DEFLECTION_KEY, DEFAULT_STL_LINEAR_DEFLECTION),
        ),
        stl_angular_deflection=max(
            0.01,
            params.GetFloat(STL_ANGULAR_DEFLECTION_KEY, DEFAULT_STL_ANGULAR_DEFLECTION),
        ),
        show_progress=params.GetBool(SHOW_PROGRESS_KEY, True),
        skip_unchanged=params.GetBool(SKIP_UNCHANGED_KEY, True),
        stl_use_freecad_settings=params.GetBool(STL_USE_FREECAD_SETTINGS_KEY, True),
    )


def save_export_options(options: ExportOptions) -> None:
    params = preferences()
    params.SetBool(EXPORT_STEP_KEY, options.export_step)
    params.SetBool(EXPORT_STL_KEY, options.export_stl)
    params.SetBool(SHOW_DIALOG_KEY, options.show_dialog)
    params.SetBool(ENABLED_KEY, options.enabled)
    params.SetString(OUTPUT_MODE_KEY, options.output_mode)
    params.SetString(CUSTOM_OUTPUT_DIRECTORY_KEY, options.custom_output_directory)
    params.SetString(FILENAME_TEMPLATE_KEY, options.filename_template)
    params.SetInt(HISTORY_LIMIT_KEY, max(0, options.history_limit))
    params.SetFloat(STL_LINEAR_DEFLECTION_KEY, max(0.001, options.stl_linear_deflection))
    params.SetFloat(STL_ANGULAR_DEFLECTION_KEY, max(0.01, options.stl_angular_deflection))
    params.SetBool(SHOW_PROGRESS_KEY, options.show_progress)
    params.SetBool(SKIP_UNCHANGED_KEY, options.skip_unchanged)
    params.SetBool(STL_USE_FREECAD_SETTINGS_KEY, options.stl_use_freecad_settings)


def resolve_stl_mesh_settings(options: ExportOptions) -> STLMeshSettings:
    if not options.stl_use_freecad_settings:
        return STLMeshSettings(
            source="manual",
            linear_deflection=max(0.001, options.stl_linear_deflection),
            angular_deflection=max(0.01, options.stl_angular_deflection),
        )

    mesh_params = App.ParamGet(FREECAD_MESH_PARAMETER_PATH)
    return STLMeshSettings(
        source="freecad",
        linear_deflection=max(
            0.001,
            mesh_params.GetFloat(
                FREECAD_MESH_MAX_DEVIATION_EXPORT_KEY,
                DEFAULT_STL_LINEAR_DEFLECTION,
            ),
        ),
        angular_deflection=DEFAULT_STL_ANGULAR_DEFLECTION,
    )


def stl_mesh_settings_signature(settings: STLMeshSettings) -> str:
    return f"{settings.source}:{settings.linear_deflection:g}:{settings.angular_deflection:g}"


def normalize_document_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(path))


def path_comparison_key(path: str) -> str:
    return os.path.normcase(normalize_document_path(path))


def _load_state_map() -> Dict[str, DocumentState]:
    raw = preferences().GetString(DOCUMENT_STATES_KEY, "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        App.Console.PrintWarning(
            "Auto Body Export: Failed to load saved selections. The saved state will be reset.\n"
        )
        return {}
    if not isinstance(decoded, dict):
        return {}

    states: Dict[str, DocumentState] = {}
    for value in decoded.values():
        state = DocumentState.from_json_value(value)
        if state is not None:
            state.path = normalize_document_path(state.path)
            states[path_comparison_key(state.path)] = state
    return states


def _save_state_map(states: Dict[str, DocumentState]) -> None:
    serializable = {key: state.to_json_value() for key, state in sorted(states.items())}
    preferences().SetString(
        DOCUMENT_STATES_KEY,
        json.dumps(serializable, ensure_ascii=False, separators=(",", ":")),
    )


def load_document_state(path: str) -> Optional[DocumentState]:
    return _load_state_map().get(path_comparison_key(path))


def save_document_state(state: DocumentState) -> None:
    states = _load_state_map()
    normalized_path = normalize_document_path(state.path)
    state.path = normalized_path
    states[path_comparison_key(normalized_path)] = state
    _save_state_map(states)


def list_document_states() -> List[DocumentState]:
    return sorted(_load_state_map().values(), key=lambda state: state.path.lower())


def save_document_states(states: Iterable[DocumentState]) -> None:
    state_map = _load_state_map()
    for state in states:
        normalized_path = normalize_document_path(state.path)
        state.path = normalized_path
        state_map[path_comparison_key(normalized_path)] = state
    _save_state_map(state_map)


def remove_document_states(paths: Iterable[str]) -> None:
    states = _load_state_map()
    for path in paths:
        states.pop(path_comparison_key(path), None)
    _save_state_map(states)


def clear_document_states() -> None:
    preferences().RemString(DOCUMENT_STATES_KEY)


def _direct_parent_part(obj) -> Optional[object]:
    try:
        parent_group = obj.getParentGeoFeatureGroup()
    except (AttributeError, RuntimeError):
        parent_group = None
    if parent_group is not None and getattr(parent_group, "TypeId", "") == "App::Part":
        return parent_group

    candidates = [
        parent
        for parent in getattr(obj, "InList", [])
        if getattr(parent, "TypeId", "") == "App::Part"
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: candidate.Name)[0]


def _has_body_ancestor(obj) -> bool:
    pending = list(getattr(obj, "InList", []))
    visited = set()
    while pending:
        parent = pending.pop()
        parent_name = getattr(parent, "Name", str(id(parent)))
        if parent_name in visited:
            continue
        visited.add(parent_name)
        if getattr(parent, "TypeId", "") == "PartDesign::Body":
            return True
        pending.extend(getattr(parent, "InList", []))
    return False


def _has_shape_property(obj) -> bool:
    return "Shape" in getattr(obj, "PropertiesList", ())


def build_inventory(document) -> Inventory:
    part_objects = [obj for obj in document.Objects if getattr(obj, "TypeId", "") == "App::Part"]
    body_objects = [
        obj for obj in document.Objects if getattr(obj, "TypeId", "") == "PartDesign::Body"
    ]

    parts = []
    for part in part_objects:
        parent = _direct_parent_part(part)
        parts.append(
            PartInfo(
                object_name=part.Name,
                label=part.Label or part.Name,
                parent_part_id=PART_PREFIX + parent.Name if parent is not None else None,
            )
        )

    bodies = []
    for body in body_objects:
        parent = _direct_parent_part(body)
        bodies.append(
            BodyInfo(
                object_name=body.Name,
                label=body.Label or body.Name,
                parent_part_id=PART_PREFIX + parent.Name if parent is not None else None,
            )
        )

    objects = []
    for obj in document.Objects:
        type_id = getattr(obj, "TypeId", "")
        if type_id in ("App::Part", "PartDesign::Body"):
            continue
        if not _has_shape_property(obj) or _has_body_ancestor(obj):
            continue
        parent = _direct_parent_part(obj)
        if parent is None:
            continue
        objects.append(
            ObjectInfo(
                object_name=obj.Name,
                label=obj.Label or obj.Name,
                type_id=type_id,
                parent_part_id=PART_PREFIX + parent.Name,
            )
        )

    return Inventory(
        parts=tuple(parts),
        bodies=tuple(bodies),
        objects=tuple(objects),
    )


def groupable_target_ids_by_parent(inventory: Inventory) -> Dict[str, Set[str]]:
    targets_by_parent: Dict[str, Set[str]] = {}
    for target in inventory.target_infos:
        if target.parent_part_id is None:
            continue
        targets_by_parent.setdefault(target.parent_part_id, set()).add(target.item_id)
    return {
        parent_id: target_ids
        for parent_id, target_ids in targets_by_parent.items()
        if len(target_ids) >= 2
    }


def normalize_target_groups(
    inventory: Inventory, target_groups: Iterable[Iterable[str]]
) -> List[Set[str]]:
    valid_target_ids = inventory.individual_target_ids
    parent_by_target_id = {
        target.item_id: target.parent_part_id for target in inventory.target_infos
    }
    pending_groups = []
    for group in target_groups:
        targets_by_parent: Dict[str, Set[str]] = {}
        for target_id in set(group) & valid_target_ids:
            parent_id = parent_by_target_id.get(target_id)
            if parent_id is not None:
                targets_by_parent.setdefault(parent_id, set()).add(target_id)
        pending_groups.extend(
            target_ids for target_ids in targets_by_parent.values() if len(target_ids) >= 2
        )

    normalized_groups: List[Set[str]] = []
    for pending_group in pending_groups:
        overlapping_groups = [group for group in normalized_groups if group & pending_group]
        if not overlapping_groups:
            normalized_groups.append(set(pending_group))
            continue
        merged_group = set(pending_group)
        for group in overlapping_groups:
            merged_group.update(group)
            normalized_groups.remove(group)
        normalized_groups.append(merged_group)

    return sorted(normalized_groups, key=lambda value: tuple(sorted(value)))


def _legacy_part_group_targets(inventory: Inventory, group_id: str) -> Set[str]:
    if not group_id.startswith(GROUP_PREFIX):
        return set()
    root_part_id = PART_PREFIX + group_id[len(GROUP_PREFIX) :]
    if root_part_id not in {part.item_id for part in inventory.parts}:
        return set()
    descendant_part_ids = _descendant_part_ids(inventory, root_part_id)
    return {
        target.item_id
        for target in inventory.target_infos
        if target.parent_part_id in descendant_part_ids
    }


def reconcile_document_state(
    path: str, inventory: Inventory, previous: Optional[DocumentState]
) -> Tuple[DocumentState, Set[str]]:
    normalized_path = normalize_document_path(path)
    current_ids = inventory.item_ids
    current_target_ids = inventory.individual_target_ids

    if previous is None:
        new_ids = set(current_ids)
        selected_target_ids = set(current_target_ids)
        target_groups = []
    else:
        new_ids = current_ids - previous.known_item_ids
        selected_target_ids = previous.selected_target_ids & current_target_ids
        selected_target_ids |= new_ids & current_target_ids
        target_groups = list(previous.target_groups)

        legacy_group_ids = {
            item_id for item_id in previous.selected_target_ids if item_id.startswith(GROUP_PREFIX)
        }
        for legacy_group_id in legacy_group_ids:
            legacy_targets = _legacy_part_group_targets(inventory, legacy_group_id)
            if legacy_targets:
                target_groups.append(legacy_targets)
                selected_target_ids.update(legacy_targets)

        target_groups = normalize_target_groups(inventory, target_groups)
        selected_target_ids = synchronize_group_selection(selected_target_ids, target_groups)

    return (
        DocumentState(
            path=normalized_path,
            known_item_ids=set(current_ids),
            selected_target_ids=selected_target_ids,
            target_groups=target_groups,
            enabled=previous.enabled if previous is not None else True,
            generated_files=(set(previous.generated_files) if previous is not None else set()),
            export_signatures=(dict(previous.export_signatures) if previous is not None else {}),
            managed_output_roots=(
                set(previous.managed_output_roots) if previous is not None else set()
            ),
            output_mode=(
                previous.output_mode if previous is not None else OUTPUT_MODE_INHERIT
            ),
            custom_output_directory=(
                previous.custom_output_directory if previous is not None else ""
            ),
        ),
        new_ids,
    )


def _short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def sanitize_filename_component(value: str, fallback: str) -> str:
    sanitized = INVALID_FILENAME_CHARACTERS.sub("_", str(value))
    sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(".")
    if not sanitized:
        sanitized = fallback
    if sanitized.upper() in WINDOWS_RESERVED_NAMES:
        sanitized += "_"
    return sanitized


def truncate_filename_stem(stem: str, identity: str) -> str:
    if len(stem) <= MAX_FILENAME_STEM_LENGTH:
        return stem
    suffix = "_" + _short_hash(identity)
    return stem[: MAX_FILENAME_STEM_LENGTH - len(suffix)].rstrip(" ._") + suffix


def validate_filename_template(template: str) -> bool:
    if not isinstance(template, str) or not template.strip():
        return False
    fields = set()
    try:
        for _, field_name, format_spec, conversion in string.Formatter().parse(template):
            if field_name is None:
                continue
            if field_name not in FILENAME_TEMPLATE_FIELDS:
                return False
            if format_spec or conversion:
                return False
            fields.add(field_name)
    except ValueError:
        return False
    return bool(fields)


def validate_output_directory_template(template: str) -> bool:
    if not isinstance(template, str):
        return False
    try:
        for _, field_name, format_spec, conversion in string.Formatter().parse(template):
            if field_name is None:
                continue
            if field_name not in OUTPUT_DIRECTORY_TEMPLATE_FIELDS:
                return False
            if format_spec or conversion:
                return False
    except ValueError:
        return False
    return True


def output_directory_uses_template(template: str) -> bool:
    try:
        return any(
            field_name is not None
            for _, field_name, _, _ in string.Formatter().parse(template)
        )
    except ValueError:
        return True


def _resolve_custom_output_directory(template: str, filepath: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(template.strip()))
    if not validate_output_directory_template(expanded):
        App.Console.PrintWarning(
            "Auto Body Export: The output directory template is invalid. "
            "Document-adjacent output will be used.\n"
        )
        return os.path.dirname(os.path.abspath(filepath))
    document_directory = os.path.dirname(os.path.abspath(filepath))
    document_parent_directory = os.path.dirname(document_directory)
    rendered = expanded.format(
        **{
            DOCUMENT_DIRECTORY_FIELD: document_directory,
            DOCUMENT_PARENT_DIRECTORY_FIELD: document_parent_directory,
        }
    )
    return os.path.abspath(os.path.normpath(rendered))


def render_export_stem(
    template: str,
    document_stem: str,
    part_label: Optional[str],
    target_label: str,
    target_name: str,
    identity: str,
) -> str:
    if not validate_filename_template(template):
        template = DEFAULT_FILENAME_TEMPLATE
    values = {
        "document": sanitize_filename_component(document_stem, "document"),
        "part": sanitize_filename_component(part_label or "", ""),
        "target": sanitize_filename_component(target_label, target_name),
        "name": sanitize_filename_component(target_name, "target"),
    }
    rendered = template.format(**values)
    rendered = sanitize_filename_component(rendered, "export")
    rendered = re.sub(r"_{2,}", "_", rendered).strip(" _")
    return truncate_filename_stem(rendered or "export", identity)


def compose_export_stem(
    document_stem: str,
    part_label: Optional[str],
    body_label: str,
    body_fallback: str,
    part_fallback: Optional[str] = None,
) -> str:
    return render_export_stem(
        DEFAULT_FILENAME_TEMPLATE,
        document_stem,
        part_label,
        body_label,
        body_fallback,
        "|".join(
            (
                document_stem,
                part_label or part_fallback or "",
                body_label,
                body_fallback,
            )
        ),
    )


def group_filename_component(source_infos: Sequence[object]) -> Tuple[str, str]:
    body_infos = [
        target for target in source_infos if getattr(target, "item_id", "").startswith(BODY_PREFIX)
    ]
    if not body_infos:
        return "Group", "Group"
    return (
        "_".join(target.label for target in body_infos),
        "_".join(target.object_name for target in body_infos),
    )


def latest_export_path(directory: str, stem: str, extension: str) -> str:
    extension = extension.lower().lstrip(".")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{stem}.{extension}")


def next_old_version_number(directory: str) -> int:
    old_versions_directory = os.path.join(directory, "old_versions")
    if not os.path.isdir(old_versions_directory):
        return 0
    version_pattern = re.compile(r"^v(?P<version>[0-9]+)$", re.IGNORECASE)
    versions = []
    for name in os.listdir(old_versions_directory):
        path = os.path.join(old_versions_directory, name)
        match = version_pattern.match(name)
        if match is not None and os.path.isdir(path):
            versions.append(int(match.group("version")))
    return max(versions) + 1 if versions else 0


def archived_export_path(output_path: str, version: int) -> str:
    directory = os.path.dirname(output_path)
    filename = os.path.basename(output_path)
    stem, extension = os.path.splitext(filename)
    archive_directory = os.path.join(directory, "old_versions", f"v{version}")
    os.makedirs(archive_directory, exist_ok=True)
    return os.path.join(
        archive_directory,
        f"{stem}_v{version}{extension}",
    )


def replace_latest_export(
    temporary_path: str, output_path: str, version: Optional[int]
) -> Optional[str]:
    if not os.path.exists(output_path):
        os.replace(temporary_path, output_path)
        return None

    if version is None:
        version = next_old_version_number(os.path.dirname(output_path))
    archive_path = archived_export_path(output_path, version)
    os.replace(output_path, archive_path)
    try:
        os.replace(temporary_path, output_path)
    except Exception:
        os.replace(archive_path, output_path)
        raise
    return archive_path


def prune_old_versions(directory: str, history_limit: int) -> None:
    old_versions_directory = os.path.join(directory, "old_versions")
    if not os.path.isdir(old_versions_directory):
        return
    version_pattern = re.compile(r"^v(?P<version>[0-9]+)$", re.IGNORECASE)
    version_directories = []
    for name in os.listdir(old_versions_directory):
        match = version_pattern.match(name)
        path = os.path.join(old_versions_directory, name)
        if match is not None and os.path.isdir(path):
            version_directories.append((int(match.group("version")), path))
    version_directories.sort()
    remove_count = max(0, len(version_directories) - max(0, history_limit))
    for _, path in version_directories[:remove_count]:
        resolved = os.path.abspath(path)
        allowed_root = os.path.abspath(old_versions_directory) + os.sep
        if resolved.startswith(allowed_root):
            shutil.rmtree(resolved)
    if not os.listdir(old_versions_directory):
        os.rmdir(old_versions_directory)


def _effective_output_settings(
    options: ExportOptions, document_state: Optional[DocumentState]
) -> Tuple[str, str, bool]:
    if document_state is not None and document_state.output_mode in (
        OUTPUT_MODE_DOCUMENT,
        OUTPUT_MODE_CUSTOM,
    ):
        return (
            document_state.output_mode,
            document_state.custom_output_directory,
            True,
        )
    return options.output_mode, options.custom_output_directory, False


def resolve_output_root(
    filepath: str,
    options: ExportOptions,
    document_state: Optional[DocumentState] = None,
) -> str:
    output_mode, custom_output_directory, uses_document_state = _effective_output_settings(
        options, document_state
    )
    if output_mode == OUTPUT_MODE_CUSTOM and custom_output_directory.strip():
        custom_root = _resolve_custom_output_directory(custom_output_directory, filepath)
        if uses_document_state or output_directory_uses_template(custom_output_directory):
            return custom_root
        document_stem = sanitize_filename_component(
            os.path.splitext(os.path.basename(filepath))[0], "document"
        )
        document_directory = os.path.dirname(path_comparison_key(filepath))
        document_subdirectory = f"{document_stem}_{_short_hash(document_directory)}"
        return os.path.abspath(os.path.join(custom_root, document_subdirectory))
    return os.path.dirname(os.path.abspath(filepath))


def _part_for_parent_id(inventory: Inventory, parent_part_id: Optional[str]) -> Optional[PartInfo]:
    if parent_part_id is None:
        return None
    return next(
        (part for part in inventory.parts if part.item_id == parent_part_id),
        None,
    )


def _descendant_part_ids(inventory: Inventory, root_part_id: str) -> Set[str]:
    descendant_ids = {root_part_id}
    changed = True
    while changed:
        changed = False
        for part in inventory.parts:
            if part.parent_part_id in descendant_ids and part.item_id not in descendant_ids:
                descendant_ids.add(part.item_id)
                changed = True
    return descendant_ids


def synchronize_group_selection(
    selected_target_ids: Iterable[str], target_groups: Iterable[Iterable[str]]
) -> Set[str]:
    synchronized_ids = set(selected_target_ids)
    for group in target_groups:
        group_ids = set(group)
        if synchronized_ids & group_ids:
            synchronized_ids.update(group_ids)
    return synchronized_ids


def build_group_visuals(
    target_groups: Iterable[Iterable[str]],
) -> Dict[str, Tuple[str, str]]:
    visuals = {}
    sorted_groups = sorted(
        (set(group) for group in target_groups if len(set(group)) >= 2),
        key=lambda value: tuple(sorted(value)),
    )
    for index, group in enumerate(sorted_groups, start=1):
        color = GROUP_COLORS[(index - 1) % len(GROUP_COLORS)]
        label = tr("Group {number} - {count} items").format(number=index, count=len(group))
        for target_id in group:
            visuals[target_id] = (label, color)
    return visuals


def _validated_export_object(document, object_name: str, label: str):
    obj = document.getObject(object_name)
    if obj is None:
        return None, f"{label}: Object not found"
    try:
        shape = obj.Shape
        if shape.isNull():
            return None, f"{label}: Shape is empty"
    except (AttributeError, RuntimeError) as error:
        return None, f"{label}: Failed to access Shape ({error})"
    return obj, None


def _global_shape(obj):
    shape = obj.Shape.copy()
    try:
        shape.Placement = obj.getGlobalPlacement()
    except (AttributeError, RuntimeError):
        shape.Placement = getattr(obj, "Placement", App.Placement())
    if shape.isNull():
        raise ValueError(f"{getattr(obj, 'Label', obj.Name)}: Shape is empty")
    return shape


def _compound_for_objects(source_objects: Sequence[object]):
    import Part

    return Part.makeCompound([_global_shape(obj) for obj in source_objects])


def _shape_signature(source_objects: Sequence[object]) -> str:
    compound = _compound_for_objects(source_objects)
    brep = compound.exportBrepToString()
    if isinstance(brep, str):
        brep = brep.encode("utf-8")
    return hashlib.sha256(brep).hexdigest()


def _build_export_plans(
    document,
    filepath: str,
    inventory: Inventory,
    selected_target_ids: Set[str],
    target_groups: Iterable[Iterable[str]],
    filename_template: str,
) -> Tuple[List[ExportTargetPlan], List[str]]:
    failures: List[str] = []
    plans: List[ExportTargetPlan] = []
    document_stem = os.path.splitext(os.path.basename(filepath))[0]
    normalized_groups = normalize_target_groups(inventory, target_groups)
    selected_target_ids = synchronize_group_selection(selected_target_ids, normalized_groups)
    grouped_target_ids = {target_id for group in normalized_groups for target_id in group}

    for target_info in inventory.target_infos:
        if (
            target_info.item_id not in selected_target_ids
            or target_info.item_id in grouped_target_ids
        ):
            continue
        target_object, failure = _validated_export_object(
            document, target_info.object_name, target_info.label
        )
        if failure is not None:
            failures.append(failure)
            continue
        try:
            signature_base = _shape_signature((target_object,))
        except Exception as error:
            failures.append(f"{target_info.label}: Failed to prepare geometry ({error})")
            continue
        part_info = _part_for_parent_id(inventory, target_info.parent_part_id)
        identity = target_info.item_id
        stem = render_export_stem(
            filename_template,
            document_stem,
            part_info.label if part_info is not None else None,
            target_info.label,
            target_info.object_name,
            identity,
        )
        plans.append(
            ExportTargetPlan(
                target_ids=(target_info.item_id,),
                source_infos=(target_info,),
                source_objects=(target_object,),
                display_label=target_info.label,
                stem=stem,
                signature_base=signature_base,
            )
        )

    for group in normalized_groups:
        if not group & selected_target_ids:
            continue
        source_infos = tuple(target for target in inventory.target_infos if target.item_id in group)
        if not source_infos:
            continue
        display_label = " + ".join(target.label for target in source_infos)
        source_objects = []
        group_failures = []
        for source_info in source_infos:
            source_object, failure = _validated_export_object(
                document, source_info.object_name, source_info.label
            )
            if failure is not None:
                group_failures.append(failure)
            else:
                source_objects.append(source_object)
        if group_failures:
            failures.append(
                f"{display_label} (group): "
                + "; ".join(group_failures)
                + ". No group file was written."
            )
            continue
        try:
            signature_base = _shape_signature(source_objects)
        except Exception as error:
            failures.append(
                f"{display_label} (group): Failed to prepare geometry "
                f"({error}). No group file was written."
            )
            continue
        part_info = _part_for_parent_id(inventory, source_infos[0].parent_part_id)
        filename_label, filename_fallback = group_filename_component(source_infos)
        target_ids = tuple(sorted(group))
        identity = "|".join(target_ids)
        plans.append(
            ExportTargetPlan(
                target_ids=target_ids,
                source_infos=source_infos,
                source_objects=tuple(source_objects),
                display_label=f"{display_label} (group)",
                stem=render_export_stem(
                    filename_template,
                    document_stem,
                    part_info.label if part_info is not None else None,
                    filename_label,
                    filename_fallback,
                    identity,
                ),
                signature_base=signature_base,
            )
        )

    plans_by_stem: Dict[str, List[ExportTargetPlan]] = {}
    for plan in plans:
        plans_by_stem.setdefault(plan.stem.casefold(), []).append(plan)
    for colliding_plans in plans_by_stem.values():
        if len(colliding_plans) < 2:
            continue
        for plan in colliding_plans:
            identity = "|".join(plan.target_ids)
            suffix = "_" + _short_hash(identity)
            plan.stem = truncate_filename_stem(
                plan.stem[: MAX_FILENAME_STEM_LENGTH - len(suffix)].rstrip(" ._") + suffix,
                identity,
            )
    return plans, failures


def _formats_for_options(options: ExportOptions) -> List[str]:
    formats = []
    if options.export_step:
        formats.append("step")
    if options.export_stl:
        formats.append("stl")
    return formats


def _protect_unmanaged_output_names(
    plans: Sequence[ExportTargetPlan],
    output_root: str,
    formats: Sequence[str],
    managed_files: Set[str],
) -> None:
    managed_file_keys = {path_comparison_key(path) for path in managed_files}
    reserved_paths: Set[str] = set()
    for plan in plans:
        identity = "|".join(plan.target_ids)
        candidate_stem = plan.stem
        attempt = 0
        while True:
            candidate_paths = [
                normalize_document_path(
                    os.path.join(output_root, extension, f"{candidate_stem}.{extension}")
                )
                for extension in formats
            ]
            candidate_keys = [path_comparison_key(path) for path in candidate_paths]
            conflicts = [
                path
                for path, key in zip(candidate_paths, candidate_keys)
                if key in reserved_paths or (os.path.exists(path) and key not in managed_file_keys)
            ]
            if not conflicts:
                plan.stem = candidate_stem
                reserved_paths.update(candidate_keys)
                break
            attempt += 1
            suffix = "_" + _short_hash(f"{identity}|{attempt}")
            base = plan.stem[: MAX_FILENAME_STEM_LENGTH - len(suffix)].rstrip(" ._")
            candidate_stem = base + suffix


def _export_step(source_objects: Sequence[object], temporary_path: str) -> None:
    _compound_for_objects(source_objects).exportStep(temporary_path)


def _export_stl(
    source_objects: Sequence[object],
    temporary_path: str,
    settings: STLMeshSettings,
) -> None:
    import MeshPart

    compound = _compound_for_objects(source_objects)
    mesh = MeshPart.meshFromShape(
        Shape=compound,
        LinearDeflection=settings.linear_deflection,
        AngularDeflection=settings.angular_deflection,
        Relative=False,
    )
    if mesh.CountFacets <= 0:
        raise RuntimeError("Generated mesh is empty")
    mesh.write(temporary_path)


def _replace_with_history(
    temporary_path: str,
    output_path: str,
    history_limit: int,
    archive_versions: Dict[str, int],
) -> Optional[str]:
    if not os.path.exists(output_path):
        os.replace(temporary_path, output_path)
        return None
    if history_limit <= 0:
        os.replace(temporary_path, output_path)
        return None
    directory = os.path.dirname(output_path)
    archive_version = archive_versions.setdefault(
        path_comparison_key(directory), next_old_version_number(directory)
    )
    return replace_latest_export(temporary_path, output_path, archive_version)


def _retire_managed_file(
    path: str,
    history_limit: int,
    archive_versions: Dict[str, int],
) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    if history_limit <= 0:
        os.remove(path)
        return None
    directory = os.path.dirname(path)
    version = archive_versions.setdefault(
        path_comparison_key(directory), next_old_version_number(directory)
    )
    archive_path = archived_export_path(path, version)
    os.replace(path, archive_path)
    return archive_path


def _is_managed_export_path(path: str, output_root: str) -> bool:
    normalized_path = normalize_document_path(path)
    normalized_root = normalize_document_path(output_root)
    try:
        relative_path = os.path.relpath(normalized_path, normalized_root)
    except ValueError:
        return False
    parts = relative_path.split(os.sep)
    if len(parts) != 2 or parts[0] not in {"step", "stl"}:
        return False
    extension = os.path.splitext(parts[1])[1].lower().lstrip(".")
    return extension == parts[0]


def _managed_output_root(path: str, allowed_roots: Iterable[str]) -> Optional[str]:
    for output_root in allowed_roots:
        if _is_managed_export_path(path, output_root):
            return normalize_document_path(output_root)
    return None


def _run_export_selected_targets(
    document,
    filepath: str,
    inventory: Inventory,
    selected_target_ids: Set[str],
    target_groups: Iterable[Iterable[str]],
    options: ExportOptions,
    previous_managed_files: Iterable[str] = (),
    previous_signatures: Optional[Dict[str, str]] = None,
    previous_output_roots: Iterable[str] = (),
    protect_unmanaged: bool = True,
    progress=None,
    document_state: Optional[DocumentState] = None,
) -> ExportRunResult:
    result = ExportRunResult()
    previous_signatures = previous_signatures or {}
    previous_signatures_by_key = {
        path_comparison_key(path): signature for path, signature in previous_signatures.items()
    }
    formats = _formats_for_options(options)
    stl_mesh_settings = resolve_stl_mesh_settings(options) if "stl" in formats else None
    output_root = resolve_output_root(filepath, options, document_state)
    allowed_output_roots = {
        normalize_document_path(output_root),
        *(normalize_document_path(path) for path in previous_output_roots if path),
    }
    managed_files_by_key = {
        path_comparison_key(path): normalize_document_path(path)
        for path in previous_managed_files
        if _managed_output_root(path, allowed_output_roots) is not None
    }
    managed_files = set(managed_files_by_key.values())
    plans, plan_failures = _build_export_plans(
        document,
        filepath,
        inventory,
        selected_target_ids,
        target_groups,
        options.filename_template,
    )
    result.failures.extend(plan_failures)
    if protect_unmanaged:
        _protect_unmanaged_output_names(plans, output_root, formats, managed_files)
    if progress is not None and hasattr(progress, "start"):
        progress.start(len(plans) * len(formats))
    archive_versions: Dict[str, int] = {}
    touched_directories: Set[str] = set()

    for plan in plans:
        for extension in formats:
            progress_label = f"{plan.display_label} ({extension.upper()})"
            continue_export = True
            if progress is not None:
                if hasattr(progress, "advance"):
                    continue_export = progress.advance(progress_label)
                else:
                    continue_export = progress(progress_label)
            if not continue_export:
                result.canceled = True
                result.failures.append("Export canceled by the user")
                break
            export_directory = os.path.join(output_root, extension)
            output_path = latest_export_path(export_directory, plan.stem, extension)
            normalized_output_path = normalize_document_path(output_path)
            output_path_key = path_comparison_key(output_path)
            signature = f"{extension}:{plan.signature_base}"
            if extension == "stl" and stl_mesh_settings is not None:
                signature += ":" + stl_mesh_settings_signature(stl_mesh_settings)
            if (
                options.skip_unchanged
                and os.path.isfile(output_path)
                and previous_signatures_by_key.get(output_path_key) == signature
            ):
                result.generated_files.add(normalized_output_path)
                result.export_signatures[normalized_output_path] = signature
                touched_directories.add(export_directory)
                App.Console.PrintMessage(f"Auto Body Export: Unchanged, skipped -> {output_path}\n")
                continue

            temporary_path = os.path.join(
                export_directory,
                f".abe-{uuid.uuid4().hex[:12]}.{extension}",
            )
            try:
                if extension == "step":
                    _export_step(plan.source_objects, temporary_path)
                else:
                    _export_stl(plan.source_objects, temporary_path, stl_mesh_settings)
                archive_path = _replace_with_history(
                    temporary_path,
                    output_path,
                    options.history_limit,
                    archive_versions,
                )
                temporary_path = ""
                if archive_path is not None:
                    App.Console.PrintMessage(
                        f"Auto Body Export: Archived previous file -> {archive_path}\n"
                    )
                App.Console.PrintMessage(
                    f"Auto Body Export: {plan.display_label} -> {output_path}\n"
                )
                result.generated_files.add(normalized_output_path)
                result.export_signatures[normalized_output_path] = signature
                touched_directories.add(export_directory)
            except Exception as error:
                result.failures.append(f"{plan.display_label} ({extension.upper()}): {error}")
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    try:
                        os.remove(temporary_path)
                    except OSError:
                        pass
        if result.canceled:
            break

    if not result.failures and not result.canceled:
        generated_file_keys = {path_comparison_key(path) for path in result.generated_files}
        stale_files = {
            path for key, path in managed_files_by_key.items() if key not in generated_file_keys
        }
        for stale_path in sorted(stale_files):
            try:
                archive_path = _retire_managed_file(
                    stale_path, options.history_limit, archive_versions
                )
                if archive_path is not None:
                    App.Console.PrintMessage(
                        f"Auto Body Export: Archived obsolete file -> {archive_path}\n"
                    )
                touched_directories.add(os.path.dirname(stale_path))
            except OSError as error:
                result.failures.append(f"Failed to retire obsolete file {stale_path}: {error}")
    if result.failures or result.canceled:
        result.generated_files.update(path for path in managed_files if os.path.isfile(path))
        for path in result.generated_files:
            path_key = path_comparison_key(path)
            if path not in result.export_signatures and path_key in previous_signatures_by_key:
                result.export_signatures[path] = previous_signatures_by_key[path_key]

    for directory in touched_directories:
        try:
            prune_old_versions(directory, options.history_limit)
        except OSError as error:
            result.failures.append(f"Failed to prune export history in {directory}: {error}")
    result.managed_output_roots = {
        root
        for path in result.generated_files
        if (root := _managed_output_root(path, allowed_output_roots)) is not None
    }
    return result


def _export_object_list(
    document_directory: str,
    export_stem: str,
    display_label: str,
    source_objects: Sequence[object],
    export_step: bool,
    export_stl: bool,
    archive_versions: Optional[Dict[str, int]] = None,
) -> List[str]:
    options = ExportOptions(
        export_step=export_step,
        export_stl=export_stl,
        show_dialog=False,
        enabled=True,
    )
    failures = []
    for extension in _formats_for_options(options):
        export_directory = os.path.join(document_directory, extension)
        output_path = latest_export_path(export_directory, export_stem, extension)
        temporary_path = os.path.join(
            export_directory,
            f".{export_stem}.{uuid.uuid4().hex}.{extension}",
        )
        try:
            if extension == "step":
                _export_step(source_objects, temporary_path)
            else:
                _export_stl(source_objects, temporary_path, resolve_stl_mesh_settings(options))
            version_map = archive_versions if archive_versions is not None else {}
            archive_path = _replace_with_history(
                temporary_path, output_path, options.history_limit, version_map
            )
            temporary_path = ""
            if archive_path is not None:
                App.Console.PrintMessage(
                    f"Auto Body Export: Archived previous file -> {archive_path}\n"
                )
            App.Console.PrintMessage(f"Auto Body Export: {display_label} -> {output_path}\n")
        except Exception as error:
            failures.append(f"{display_label} ({extension.upper()}): {error}")
        finally:
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
    return failures


def _export_selected_targets(
    document,
    filepath: str,
    inventory: Inventory,
    selected_target_ids: Set[str],
    export_step: bool,
    export_stl: bool,
    target_groups: Iterable[Iterable[str]] = (),
) -> List[str]:
    options = ExportOptions(
        export_step=export_step,
        export_stl=export_stl,
        show_dialog=False,
        enabled=True,
    )
    return _run_export_selected_targets(
        document=document,
        filepath=filepath,
        inventory=inventory,
        selected_target_ids=selected_target_ids,
        target_groups=target_groups,
        options=options,
        protect_unmanaged=False,
    ).failures


def _export_selected_bodies(
    document,
    filepath: str,
    inventory: Inventory,
    selected_body_ids: Set[str],
    export_step: bool,
    export_stl: bool,
) -> List[str]:
    return _export_selected_targets(
        document=document,
        filepath=filepath,
        inventory=inventory,
        selected_target_ids=selected_body_ids,
        export_step=export_step,
        export_stl=export_stl,
    )


class SelectionDialog:
    def __init__(
        self,
        document_label: str,
        inventory: Inventory,
        selected_target_ids: Set[str],
        target_groups: Iterable[Iterable[str]],
        new_item_ids: Set[str],
        options: ExportOptions,
        document_enabled: bool = True,
        document_output_mode: str = OUTPUT_MODE_INHERIT,
        document_custom_output_directory: str = "",
        document_path: str = "",
    ):
        from PySide import QtCore, QtGui, QtWidgets

        self.QtCore = QtCore
        self.QtGui = QtGui
        self.QtWidgets = QtWidgets
        self.inventory = inventory
        self._updating_tree = False
        self._target_items: Dict[str, object] = {}
        self._target_infos = {target.item_id: target for target in inventory.target_infos}
        self._target_groups = normalize_target_groups(inventory, target_groups)
        self._group_buttons: Dict[str, object] = {}
        self._group_checkboxes: Dict[Tuple[str, str], object] = {}
        self._document_path = document_path

        dialog_parent = None
        try:
            import FreeCADGui as Gui

            dialog_parent = Gui.getMainWindow()
        except (ImportError, RuntimeError):
            pass
        self.dialog = QtWidgets.QDialog(dialog_parent)
        self.dialog.setWindowTitle(tr("Auto Body Export"))
        self.dialog.resize(780, 540)

        root_layout = QtWidgets.QVBoxLayout(self.dialog)
        description = QtWidgets.QLabel(
            tr(
                'Select the Bodies and independent objects to export from "{document}". '
                "Use the Group column to export multiple targets in the same Part as one file."
            ).format(document=document_label)
        )
        description.setWordWrap(True)
        root_layout.addWidget(description)

        self.document_enabled_checkbox = QtWidgets.QCheckBox(
            tr("Enable automatic export for this document")
        )
        self.document_enabled_checkbox.setChecked(document_enabled)
        root_layout.addWidget(self.document_enabled_checkbox)

        output_group = QtWidgets.QGroupBox(tr("Output location for this document"))
        output_layout = QtWidgets.QGridLayout(output_group)
        self.document_output_mode_combo = QtWidgets.QComboBox()
        self.document_output_mode_combo.addItem(
            tr("Use global preference"),
            OUTPUT_MODE_INHERIT,
        )
        self.document_output_mode_combo.addItem(
            tr("Beside this document"),
            OUTPUT_MODE_DOCUMENT,
        )
        self.document_output_mode_combo.addItem(tr("Custom directory"), OUTPUT_MODE_CUSTOM)
        output_layout.addWidget(self.document_output_mode_combo, 0, 0, 1, 3)

        self.document_custom_output_edit = QtWidgets.QLineEdit()
        self.document_custom_output_edit.setPlaceholderText(DOCUMENT_DIRECTORY_TOKEN + "/export")
        default_custom_directory = (
            document_custom_output_directory
            if document_custom_output_directory
            else options.custom_output_directory
        )
        self.document_custom_output_edit.setText(default_custom_directory)
        self.document_custom_output_button = QtWidgets.QPushButton(tr("Browse..."))
        self.document_custom_output_button.clicked.connect(
            self._browse_document_output_directory
        )
        output_layout.addWidget(self.document_custom_output_edit, 1, 0, 1, 2)
        output_layout.addWidget(self.document_custom_output_button, 1, 2)

        output_note = QtWidgets.QLabel(
            tr(
                "Use {document_dir} for the current document directory, "
                "{document_parent_dir} for its parent, or .. for relative paths."
            )
        )
        output_note.setWordWrap(True)
        output_layout.addWidget(output_note, 2, 0, 1, 3)
        root_layout.addWidget(output_group)

        output_index = self.document_output_mode_combo.findData(document_output_mode)
        if output_index < 0:
            output_index = 0
        self.document_output_mode_combo.setCurrentIndex(output_index)
        self.document_output_mode_combo.currentIndexChanged.connect(
            self._update_document_output_controls
        )
        self._update_document_output_controls()

        format_group = QtWidgets.QGroupBox(tr("File formats"))
        format_layout = QtWidgets.QHBoxLayout(format_group)
        self.step_checkbox = QtWidgets.QCheckBox("STEP")
        self.step_checkbox.setChecked(options.export_step)
        self.stl_checkbox = QtWidgets.QCheckBox("STL")
        self.stl_checkbox.setChecked(options.export_stl)
        format_layout.addWidget(self.step_checkbox)
        format_layout.addWidget(self.stl_checkbox)
        format_layout.addStretch()
        root_layout.addWidget(format_group)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(
            [
                tr("Part / Export target"),
                tr("Type"),
                tr("Group"),
                tr("Status"),
            ]
        )
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        root_layout.addWidget(self.tree, 1)

        selection_buttons = QtWidgets.QHBoxLayout()
        select_all_button = QtWidgets.QPushButton(tr("Select all"))
        select_all_button.clicked.connect(lambda: self._set_all_targets(True))
        clear_all_button = QtWidgets.QPushButton(tr("Clear all"))
        clear_all_button.clicked.connect(lambda: self._set_all_targets(False))
        selection_buttons.addWidget(select_all_button)
        selection_buttons.addWidget(clear_all_button)
        selection_buttons.addStretch()
        root_layout.addLayout(selection_buttons)

        self.hide_dialog_checkbox = QtWidgets.QCheckBox(tr("Do not show this dialog next time"))
        self.hide_dialog_checkbox.setChecked(not options.show_dialog)
        root_layout.addWidget(self.hide_dialog_checkbox)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setText(tr("OK"))
        self.button_box.button(QtWidgets.QDialogButtonBox.Cancel).setText(tr("Cancel"))
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.dialog.reject)
        root_layout.addWidget(self.button_box)

        self._populate_tree(selected_target_ids, new_item_ids)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.expandAll()
        for column in range(4):
            self.tree.resizeColumnToContents(column)
        self.tree.setColumnWidth(2, max(self.tree.columnWidth(2), 170))

    def _check_state(self, checked: bool):
        return self.QtCore.Qt.Checked if checked else self.QtCore.Qt.Unchecked

    def _item_kind(self, item) -> str:
        return item.data(0, self.QtCore.Qt.UserRole) or ""

    def _populate_tree(self, selected_target_ids: Set[str], new_item_ids: Set[str]) -> None:
        part_items: Dict[str, object] = {}
        part_by_id = {part.item_id: part for part in self.inventory.parts}

        def create_part_item(part: PartInfo, visiting: Set[str]):
            if part.item_id in part_items:
                return part_items[part.item_id]
            if part.item_id in visiting:
                parent_item = self.tree.invisibleRootItem()
            elif part.parent_part_id is not None and part.parent_part_id in part_by_id:
                parent_item = create_part_item(
                    part_by_id[part.parent_part_id], visiting | {part.item_id}
                )
            else:
                parent_item = self.tree.invisibleRootItem()

            item = self.QtWidgets.QTreeWidgetItem(parent_item)
            item.setText(0, part.label)
            item.setText(1, tr("Part"))
            item.setData(0, self.QtCore.Qt.UserRole, "part")
            item.setData(0, self.QtCore.Qt.UserRole + 1, part.item_id)
            if part.item_id in new_item_ids:
                self._mark_new(item)
            part_items[part.item_id] = item
            return item

        for part in sorted(
            self.inventory.parts,
            key=lambda value: (value.label.lower(), value.object_name),
        ):
            create_part_item(part, set())

        unparented_item = None
        unparented_bodies = [body for body in self.inventory.bodies if body.parent_part_id is None]
        if unparented_bodies:
            unparented_item = self.QtWidgets.QTreeWidgetItem(self.tree.invisibleRootItem())
            unparented_item.setText(0, tr("No Part"))
            unparented_item.setText(1, tr("Group"))
            unparented_item.setData(0, self.QtCore.Qt.UserRole, "part")
            unparented_item.setData(0, self.QtCore.Qt.UserRole + 1, UNPARENTED_GROUP_ID)

        for body in sorted(
            self.inventory.bodies,
            key=lambda value: (value.label.lower(), value.object_name),
        ):
            parent_item = (
                part_items.get(body.parent_part_id)
                if body.parent_part_id is not None
                else unparented_item
            )
            if parent_item is None:
                parent_item = self.tree.invisibleRootItem()
            item = self.QtWidgets.QTreeWidgetItem(parent_item)
            item.setText(0, body.label)
            item.setText(1, tr("Body"))
            item.setData(0, self.QtCore.Qt.UserRole, "body")
            item.setData(0, self.QtCore.Qt.UserRole + 1, body.item_id)
            item.setFlags(item.flags() | self.QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, self._check_state(body.item_id in selected_target_ids))
            if body.item_id in new_item_ids:
                self._mark_new(item)
            self._target_items[body.item_id] = item

        for object_info in sorted(
            self.inventory.objects,
            key=lambda value: (value.label.lower(), value.object_name),
        ):
            parent_item = part_items.get(object_info.parent_part_id)
            if parent_item is None:
                continue
            item = self.QtWidgets.QTreeWidgetItem(parent_item)
            item.setText(0, object_info.label)
            item.setText(1, tr("Object"))
            item.setData(0, self.QtCore.Qt.UserRole, "object")
            item.setData(0, self.QtCore.Qt.UserRole + 1, object_info.item_id)
            item.setFlags(item.flags() | self.QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, self._check_state(object_info.item_id in selected_target_ids))
            item.setToolTip(0, object_info.type_id)
            if object_info.item_id in new_item_ids:
                self._mark_new(item)
            self._target_items[object_info.item_id] = item

        self._create_group_menus()
        self._synchronize_all_group_selections()
        self._refresh_all_part_states()

    def _group_for_target(self, target_id: str) -> Optional[Set[str]]:
        return next(
            (group for group in self._target_groups if target_id in group),
            None,
        )

    def _create_group_menus(self) -> None:
        targets_by_parent = groupable_target_ids_by_parent(self.inventory)
        for target_id, item in self._target_items.items():
            target_info = self._target_infos[target_id]
            candidate_ids = targets_by_parent.get(target_info.parent_part_id, set())
            if len(candidate_ids) < 2:
                continue

            button = self.QtWidgets.QToolButton(self.tree)
            button.setMinimumWidth(150)
            button.setPopupMode(self.QtWidgets.QToolButton.InstantPopup)
            button.setToolButtonStyle(self.QtCore.Qt.ToolButtonTextOnly)
            menu = self.QtWidgets.QMenu(button)
            panel = self.QtWidgets.QWidget(menu)
            panel.setMinimumWidth(220)
            panel_layout = self.QtWidgets.QVBoxLayout(panel)
            panel_layout.setContentsMargins(8, 6, 8, 6)
            panel_layout.setSpacing(2)

            heading = self.QtWidgets.QLabel(tr("Export in the same file as this row"))
            heading_font = heading.font()
            heading_font.setBold(True)
            heading.setFont(heading_font)
            panel_layout.addWidget(heading)

            candidate_infos = sorted(
                (
                    self._target_infos[candidate_id]
                    for candidate_id in candidate_ids
                    if candidate_id != target_id
                ),
                key=lambda target: (target.label.lower(), target.object_name),
            )
            for candidate_info in candidate_infos:
                checkbox = self.QtWidgets.QCheckBox(candidate_info.label, panel)
                checkbox.setToolTip(candidate_info.object_name)
                checkbox.toggled.connect(
                    lambda checked, source_id=target_id, candidate_id=candidate_info.item_id: (
                        self._toggle_group_member(source_id, candidate_id, checked)
                    )
                )
                panel_layout.addWidget(checkbox)
                self._group_checkboxes[(target_id, candidate_info.item_id)] = checkbox

            widget_action = self.QtWidgets.QWidgetAction(menu)
            widget_action.setDefaultWidget(panel)
            menu.addAction(widget_action)
            button.setMenu(menu)
            self.tree.setItemWidget(item, 2, button)
            self._group_buttons[target_id] = button

        self._refresh_group_widgets()

    def _toggle_group_member(self, source_id: str, candidate_id: str, checked: bool) -> None:
        if self._updating_tree:
            return

        source_group = self._group_for_target(source_id)
        candidate_group = self._group_for_target(candidate_id)
        if checked:
            merged_group = {source_id, candidate_id}
            remaining_groups = []
            for group in self._target_groups:
                if source_id in group or candidate_id in group:
                    merged_group.update(group)
                else:
                    remaining_groups.append(set(group))
            remaining_groups.append(merged_group)
            self._target_groups = normalize_target_groups(self.inventory, remaining_groups)
        elif source_group is not None and candidate_id in source_group:
            remaining_group = set(source_group) - {candidate_id}
            self._target_groups = [
                set(group) for group in self._target_groups if group is not source_group
            ]
            if len(remaining_group) >= 2:
                self._target_groups.append(remaining_group)
            self._target_groups = normalize_target_groups(self.inventory, self._target_groups)
        elif candidate_group is not None and source_id in candidate_group:
            remaining_group = set(candidate_group) - {source_id}
            self._target_groups = [
                set(group) for group in self._target_groups if group is not candidate_group
            ]
            if len(remaining_group) >= 2:
                self._target_groups.append(remaining_group)
            self._target_groups = normalize_target_groups(self.inventory, self._target_groups)

        self._synchronize_all_group_selections()
        self._refresh_group_widgets()
        self._refresh_all_part_states()

    def _synchronize_all_group_selections(self) -> None:
        self._updating_tree = True
        try:
            for group in self._target_groups:
                group_items = [
                    self._target_items[target_id]
                    for target_id in group
                    if target_id in self._target_items
                ]
                if not group_items:
                    continue
                checked = any(item.checkState(0) == self.QtCore.Qt.Checked for item in group_items)
                state = self._check_state(checked)
                for item in group_items:
                    item.setCheckState(0, state)
        finally:
            self._updating_tree = False

    def _refresh_group_widgets(self) -> None:
        self._updating_tree = True
        try:
            group_visuals = build_group_visuals(self._target_groups)
            for (source_id, candidate_id), checkbox in self._group_checkboxes.items():
                source_group = self._group_for_target(source_id)
                checkbox.setChecked(source_group is not None and candidate_id in source_group)

            for target_id, button in self._group_buttons.items():
                group = self._group_for_target(target_id)
                if group is None:
                    button.setText(tr("Individual"))
                    button.setToolTip(tr("Export this target as an individual file."))
                    button.setStyleSheet("")
                    continue
                group_label, group_color = group_visuals[target_id]
                member_labels = [
                    self._target_infos[member_id].label
                    for member_id in sorted(
                        group,
                        key=lambda member_id: (
                            self._target_infos[member_id].label.lower(),
                            self._target_infos[member_id].object_name,
                        ),
                    )
                ]
                button.setText(group_label)
                button.setStyleSheet(
                    "QToolButton {"
                    f"background-color: {group_color};"
                    "color: #202124;"
                    "border: 1px solid #5f6368;"
                    "border-radius: 3px;"
                    "font-weight: bold;"
                    "padding: 2px 6px;"
                    "}"
                    "QToolButton:hover {"
                    "border: 2px solid #202124;"
                    "}"
                )
                button.setToolTip(f"{group_label}. Exported together: " + " / ".join(member_labels))
        finally:
            self._updating_tree = False

    def _mark_new(self, item) -> None:
        background_brush = self.QtGui.QBrush(self.QtGui.QColor("#ffe082"))
        foreground_brush = self.QtGui.QBrush(self.QtGui.QColor("#202124"))
        item.setText(3, tr("NEW"))
        for column in range(4):
            item.setBackground(column, background_brush)
            item.setForeground(column, foreground_brush)
            font = item.font(column)
            font.setBold(True)
            item.setFont(column, font)

    def _descendant_individual_items(self, item) -> List[object]:
        descendants = []
        for index in range(item.childCount()):
            child = item.child(index)
            if self._item_kind(child) in ("body", "object"):
                descendants.append(child)
            elif self._item_kind(child) == "part":
                descendants.extend(self._descendant_individual_items(child))
        return descendants

    def _set_part_state_from_children(self, item) -> None:
        target_items = self._descendant_individual_items(item)
        if not target_items:
            item.setFlags(item.flags() & ~self.QtCore.Qt.ItemIsUserCheckable)
            item.setText(3, item.text(3) or tr("No targets"))
            return

        item.setFlags(item.flags() | self.QtCore.Qt.ItemIsUserCheckable)
        states = {target_item.checkState(0) for target_item in target_items}
        if states == {self.QtCore.Qt.Checked}:
            state = self.QtCore.Qt.Checked
        elif states == {self.QtCore.Qt.Unchecked}:
            state = self.QtCore.Qt.Unchecked
        else:
            state = self.QtCore.Qt.PartiallyChecked
        item.setCheckState(0, state)

    def _refresh_all_part_states(self) -> None:
        self._updating_tree = True
        try:
            root = self.tree.invisibleRootItem()
            all_items = []

            def collect(item):
                for index in range(item.childCount()):
                    child = item.child(index)
                    collect(child)
                    all_items.append(child)

            collect(root)
            for item in all_items:
                if self._item_kind(item) == "part":
                    self._set_part_state_from_children(item)
        finally:
            self._updating_tree = False

    def _on_item_changed(self, item, column: int) -> None:
        if self._updating_tree or column != 0:
            return
        self._updating_tree = True
        try:
            if self._item_kind(item) == "part":
                state = item.checkState(0)
                if state in (self.QtCore.Qt.Checked, self.QtCore.Qt.Unchecked):
                    for target_item in self._descendant_individual_items(item):
                        target_item.setCheckState(0, state)
            elif self._item_kind(item) in ("body", "object"):
                target_id = item.data(0, self.QtCore.Qt.UserRole + 1)
                group = self._group_for_target(target_id)
                if group is not None:
                    state = item.checkState(0)
                    for group_target_id in group:
                        group_item = self._target_items.get(group_target_id)
                        if group_item is not None:
                            group_item.setCheckState(0, state)
        finally:
            self._updating_tree = False
        self._refresh_all_part_states()

    def _set_all_targets(self, checked: bool) -> None:
        self._updating_tree = True
        try:
            state = self._check_state(checked)
            for item in self._target_items.values():
                item.setCheckState(0, state)
        finally:
            self._updating_tree = False
        self._refresh_all_part_states()

    def _update_document_output_controls(self) -> None:
        is_custom = self.document_output_mode_combo.currentData() == OUTPUT_MODE_CUSTOM
        self.document_custom_output_edit.setEnabled(is_custom)
        self.document_custom_output_button.setEnabled(is_custom)

    def _browse_document_output_directory(self) -> None:
        start_directory = self.document_custom_output_edit.text().strip()
        if start_directory and validate_output_directory_template(start_directory):
            start_directory = _resolve_custom_output_directory(start_directory, self._document_path)
        if not start_directory:
            start_directory = os.path.dirname(os.path.abspath(self._document_path or os.curdir))
        directory = self.QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog, tr("Custom directory"), start_directory
        )
        if directory:
            self.document_custom_output_edit.setText(directory)

    def _validate_and_accept(self) -> None:
        if not self.step_checkbox.isChecked() and not self.stl_checkbox.isChecked():
            self.QtWidgets.QMessageBox.warning(
                self.dialog,
                tr("Auto Body Export"),
                tr("Select at least one file format: STEP or STL."),
            )
            return
        if self.document_output_mode_combo.currentData() == OUTPUT_MODE_CUSTOM:
            custom_directory = self.document_custom_output_edit.text().strip()
            if not custom_directory:
                self.QtWidgets.QMessageBox.warning(
                    self.dialog,
                    tr("Auto Body Export"),
                    tr("Select a custom output directory."),
                )
                return
            if not validate_output_directory_template(custom_directory):
                self.QtWidgets.QMessageBox.warning(
                    self.dialog,
                    tr("Auto Body Export"),
                    tr(
                        "The output directory may only use {document_dir} "
                        "or {document_parent_dir}."
                    ),
                )
                return
        self.dialog.accept()

    def exec(self) -> DialogResult:
        if hasattr(self.dialog, "exec"):
            dialog_code = self.dialog.exec()
        else:
            dialog_code = self.dialog.exec_()
        accepted = dialog_code == self.QtWidgets.QDialog.Accepted
        selected_target_ids = {
            target_id
            for target_id, item in self._target_items.items()
            if item.checkState(0) == self.QtCore.Qt.Checked
        }
        return DialogResult(
            accepted=accepted,
            selected_target_ids=selected_target_ids,
            target_groups=[set(group) for group in self._target_groups],
            export_step=self.step_checkbox.isChecked(),
            export_stl=self.stl_checkbox.isChecked(),
            show_dialog=not self.hide_dialog_checkbox.isChecked(),
            document_enabled=self.document_enabled_checkbox.isChecked(),
            output_mode=self.document_output_mode_combo.currentData(),
            custom_output_directory=self.document_custom_output_edit.text().strip(),
        )


def _show_failure_summary(failures: Sequence[str]) -> None:
    if not failures:
        return
    message = (
        tr("Some targets could not be exported:")
        + "\n\n"
        + "\n".join(f"- {failure}" for failure in failures)
    )
    App.Console.PrintError("Auto Body Export:\n" + "\n".join(failures) + "\n")
    if App.GuiUp:
        from PySide import QtWidgets

        QtWidgets.QMessageBox.warning(None, tr("Auto Body Export"), message)


class ExportProgress:
    def __init__(self, enabled: bool):
        self.enabled = enabled and bool(App.GuiUp)
        self.dialog = None
        self.current = 0

    def start(self, total: int) -> None:
        if not self.enabled or total <= 1:
            return
        from PySide import QtCore, QtWidgets

        self.dialog = QtWidgets.QProgressDialog(
            tr("Exporting selected targets..."),
            tr("Cancel"),
            0,
            total,
        )
        self.dialog.setWindowTitle(tr("Auto Body Export"))
        self.dialog.setWindowModality(QtCore.Qt.WindowModal)
        self.dialog.setMinimumDuration(250)
        self.dialog.setValue(0)

    def advance(self, label: str) -> bool:
        self.current += 1
        if self.dialog is None:
            return True
        from PySide import QtWidgets

        self.dialog.setLabelText(label)
        self.dialog.setValue(self.current - 1)
        QtWidgets.QApplication.processEvents()
        return not self.dialog.wasCanceled()

    def close(self) -> None:
        if self.dialog is not None:
            self.dialog.setValue(self.dialog.maximum())
            self.dialog.close()
            self.dialog = None


def gui_is_available() -> bool:
    return bool(App.GuiUp)


def schedule_gui_task(callback) -> None:
    from PySide import QtCore

    QtCore.QTimer.singleShot(SAVE_PROCESS_DELAY_MS, callback)


def process_saved_document(document, filepath: str) -> None:
    if not filepath:
        App.Console.PrintWarning(
            "Auto Body Export: The document path is unavailable. Export was skipped.\n"
        )
        return

    options = load_export_options()
    if not options.enabled:
        return

    previous_state = load_document_state(filepath)
    if previous_state is not None and not previous_state.enabled:
        return

    inventory = build_inventory(document)
    reconciled_state, new_item_ids = reconcile_document_state(filepath, inventory, previous_state)
    must_show_dialog = options.show_dialog or previous_state is None or bool(new_item_ids)

    if must_show_dialog and App.GuiUp:
        dialog = SelectionDialog(
            document_label=document.Label or document.Name,
            inventory=inventory,
            selected_target_ids=reconciled_state.selected_target_ids,
            target_groups=reconciled_state.target_groups,
            new_item_ids=new_item_ids,
            options=options,
            document_enabled=reconciled_state.enabled,
            document_output_mode=reconciled_state.output_mode,
            document_custom_output_directory=reconciled_state.custom_output_directory,
            document_path=filepath,
        )
        result = dialog.exec()
        if not result.accepted:
            App.Console.PrintMessage("Auto Body Export: Export was canceled for this save.\n")
            return
        reconciled_state.selected_target_ids = result.selected_target_ids
        reconciled_state.target_groups = result.target_groups
        reconciled_state.enabled = result.document_enabled
        reconciled_state.output_mode = result.output_mode
        reconciled_state.custom_output_directory = result.custom_output_directory
        options = dataclass_replace(
            options,
            export_step=result.export_step,
            export_stl=result.export_stl,
            show_dialog=result.show_dialog,
        )
        save_export_options(options)
    elif must_show_dialog:
        if previous_state is None:
            App.Console.PrintWarning(
                "Auto Body Export: A GUI is required to opt this document in. Export was skipped.\n"
            )
            return
        App.Console.PrintWarning(
            "Auto Body Export: The selection dialog is unavailable without a GUI. "
            "Saved settings will be used.\n"
        )

    save_document_state(reconciled_state)
    if not reconciled_state.enabled:
        App.Console.PrintMessage(
            "Auto Body Export: Automatic export is disabled for this document.\n"
        )
        return

    if not options.export_step and not options.export_stl:
        App.Console.PrintWarning("Auto Body Export: No export format is selected.\n")
        return

    progress = ExportProgress(options.show_progress)
    try:
        run_result = _run_export_selected_targets(
            document=document,
            filepath=filepath,
            inventory=inventory,
            selected_target_ids=reconciled_state.selected_target_ids,
            target_groups=reconciled_state.target_groups,
            options=options,
            previous_managed_files=reconciled_state.generated_files,
            previous_signatures=reconciled_state.export_signatures,
            previous_output_roots=reconciled_state.managed_output_roots,
            progress=progress,
            document_state=reconciled_state,
        )
    finally:
        progress.close()
    reconciled_state.generated_files = set(run_result.generated_files)
    reconciled_state.export_signatures = dict(run_result.export_signatures)
    reconciled_state.managed_output_roots = set(run_result.managed_output_roots)
    save_document_state(reconciled_state)
    _show_failure_summary(run_result.failures)


class DocumentObserver:
    def __init__(self):
        self._processing_documents: Set[str] = set()
        self._pending_documents: Dict[str, Tuple[object, str]] = {}
        self._stopped = False
        App.addDocumentObserver(self)

    def stop(self) -> None:
        self._stopped = True
        self._pending_documents.clear()
        App.removeDocumentObserver(self)

    def slotFinishSaveDocument(self, document, filepath: str) -> None:
        document_key = getattr(document, "Name", str(id(document)))
        if self._stopped:
            return

        if gui_is_available():
            already_pending = document_key in self._pending_documents
            self._pending_documents[document_key] = (document, filepath)
            if not already_pending:
                schedule_gui_task(lambda key=document_key: self._process_pending_document(key))
            return

        self._process_document(document_key, document, filepath)

    def _process_pending_document(self, document_key: str) -> None:
        if self._stopped:
            return
        pending = self._pending_documents.pop(document_key, None)
        if pending is None:
            return
        document, filepath = pending
        self._process_document(document_key, document, filepath)

    def _process_document(self, document_key: str, document, filepath: str) -> None:
        if document_key in self._processing_documents:
            return
        self._processing_documents.add(document_key)
        try:
            process_saved_document(document, filepath)
        except Exception as error:
            App.Console.PrintError(f"Auto Body Export: Post-save processing failed: {error}\n")
            if App.GuiUp:
                from PySide import QtWidgets

                QtWidgets.QMessageBox.critical(
                    None,
                    tr("Auto Body Export"),
                    tr("Post-save processing failed.") + f"\n\n{error}",
                )
        finally:
            self._processing_documents.discard(document_key)


def initialize() -> DocumentObserver:
    global observer_singleton
    previous = globals().get("observer_singleton")
    if previous is not None:
        try:
            previous.stop()
        except Exception:
            pass
    observer_singleton = DocumentObserver()
    App.Console.PrintMessage(
        "Auto Body Export: Save observer initialized. Use Preferences to enable automatic export.\n"
    )
    return observer_singleton


observer_singleton = None
