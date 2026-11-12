"""Versioned external engine requirements, independent of Manager DLL APIs."""
from dataclasses import dataclass
from .panel_engine import PANEL_SERVICE, ACTION_SERVICE, find_panels
from .gpl_function_merge import _tokens

SERVICE_NAMES = {PANEL_SERVICE: "Custom Building Panels", ACTION_SERVICE: "Scripted Ground Actions"}


@dataclass(frozen=True)
class PatchRequirement:
    service: str
    minimum_revision: int = 1


@dataclass(frozen=True)
class RequirementEvidence:
    requirement: PatchRequirement
    owner_id: str
    owner_name: str
    dataset: str
    origin: str


def parse_requirements(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError("external_patches must be an array")
    result = []
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) - {"service", "minimum_revision"}:
            raise ValueError("external_patches expects service and optional minimum_revision")
        service = row.get("service")
        revision = row.get("minimum_revision", 1)
        if service not in SERVICE_NAMES or type(revision) is not int or not 1 <= revision <= 0xffff:
            raise ValueError("Unknown external patch service or invalid minimum_revision")
        if service in seen:
            raise ValueError("Duplicate external patch requirement: " + service)
        seen.add(service)
        result.append(PatchRequirement(service, revision))
    return tuple(result)


def requirement_mapping(requirement):
    return {"service": requirement.service, "minimum_revision": requirement.minimum_revision}


def from_effective_resources(resources, *, owner_id, owner_name, dataset):
    panels = find_panels(resources)
    if not panels:
        return ()
    revision = max(row.minimum_revision for rows in panels.values() for row in rows)
    return (RequirementEvidence(PatchRequirement(PANEL_SERVICE, revision), owner_id, owner_name,
        dataset, "loaded SMNU/STRT " + ", ".join(key.decode("latin1") for key in sorted(panels))),)


def from_verified_sources(sources, *, owner_id, owner_name, dataset):
    """Only call after sources were proven to reproduce the loaded target.

    The input is the effective source after conflict selection. Merely shipping
    an example source or a BCD definition-name index supplies no call proof.
    """
    from .gpl import parse_gpl,DefinitionKind
    sources=tuple(sources)
    functions = {'sf_mapaction': 1, 'sf_setwindow': 2, 'sf_resetwindow': 2,
                 'sf_unexploredarea': 2}
    parsed = tuple(parse_gpl(source, name) for name, source in sources)
    local = {symbol for symbol in functions if any(
        source.get(DefinitionKind.FUNCTION, symbol) is not None for source in parsed)}
    result = []
    for name, source in sources:
        tokens = _tokens(source)
        calls = {token[1:] for index, token in enumerate(tokens)
                 if token.startswith("$") and token[1:] in functions and token[1:] not in local
                 and tokens[index + 1:index + 2] == ("(",)}
        if calls:
            result.append(RequirementEvidence(PatchRequirement(ACTION_SERVICE,
                max(functions[call] for call in calls)), owner_id, owner_name,
                dataset, "verified loaded GPL call in " + name + ": " + ", ".join(sorted(calls))))
    return tuple(result)


def aggregate(evidence):
    """Retain dependent-mod attribution while taking each service's maximum."""
    rows = {}
    for item in evidence:
        row = rows.setdefault(item.requirement.service, {"revision": 0, "owners": {}})
        row["revision"] = max(row["revision"], item.requirement.minimum_revision)
        row["owners"][item.owner_id] = item.owner_name
    return tuple((PatchRequirement(service, row["revision"]), tuple(sorted(row["owners"].items())))
                 for service, row in sorted(rows.items()))


def missing(evidence, installed):
    """Installed revisions are freshly inspected for ONE chosen executable."""
    return tuple((requirement, owners) for requirement, owners in aggregate(evidence)
                 if installed.get(requirement.service, 0) < requirement.minimum_revision)


def prompt_text(requirements):
    return "These selected mods need game patches before launching:\n\n" + "\n".join(
        SERVICE_NAMES[requirement.service] + ": " + ", ".join(name for _, name in owners)
        for requirement, owners in requirements)
