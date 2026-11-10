"""Read existing, independently maintained native profile columns.

No address translation or branch delta is inferred. Consumers still verify the
referenced bytes and caller contracts against their exact executable fixtures.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRANCHES = ("public", "beta2", "gog")


def aggregate_values(text):
    result = []
    start = depth = 0
    quoted = False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        if quoted:
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    if text[start:].strip():
        result.append(text[start:].strip())
    return result


def initializer(source, label):
    match = re.search(r'\b' + re.escape(label) + r'\s*(?:=\s*)?\{', source)
    if match is None:
        raise ValueError("Missing native profile initializer: " + label)
    start = match.end()
    depth = 1
    for end in range(start, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return aggregate_values(source[start:end])
    raise ValueError("Unterminated native profile initializer: " + label)


def manager_profiles():
    source = (ROOT / 'runtime/MajestyModManagerRuntime.cpp').read_text(encoding='utf8')
    fields = re.findall(r'\b(\w+)(?:\[\d+\])?;', source.split(
        'struct MajestyBuildProfile {', 1)[1].split('};', 1)[0])
    result = {}
    for branch, label in zip(BRANCHES, ('kPublicBuildProfile', 'kBeta2BuildProfile')):
        values = initializer(source, label)
        if len(values) != len(fields):
            raise ValueError("Native profile field count changed: " + label)
        result[branch] = dict(zip(fields, values))
    # MakeGogBuildProfile starts with p{}, not a beta copy. Its explicit
    # assignments and ProfileBytes calls are the only admitted values.
    result['gog'] = {}
    overrides = source.split('constexpr MajestyBuildProfile MakeGogBuildProfile()', 1)[1].split('return p;', 1)[0]
    for field, value in re.findall(r'p\.(\w+)\s*=\s*([^;]+);', overrides):
        result['gog'][field] = value.strip()
    for field, value in re.findall(r'ProfileBytes\(p\.(\w+),\s*(\{[^}]+\})\);', overrides):
        result['gog'][field] = value
    return result


def map_query_profiles():
    source = (ROOT / 'runtime/MapQueryRuntime.cpp').read_text(encoding='utf8')
    struct = source.split('struct Profile {', 1)[1].split('};', 1)[0]
    fields = re.findall(r'\b\w+\b', re.sub(r'std::uintptr_t', '', struct))
    result = {}
    for branch, label in zip(BRANCHES, ('kPublic', 'kBeta', 'kGog')):
        values = initializer(source, label)
        if len(values) != len(fields):
            raise ValueError("Map-query profile field count changed: " + label)
        result[branch] = {field: int(value, 0) for field, value in zip(fields, values)}
    return result


def byte_array(value):
    if not value.startswith('{') or not value.endswith('}'):
        raise ValueError("Expected literal native byte guard")
    return bytes(int(item.strip(), 0) for item in value[1:-1].split(',') if item.strip())


def paid_source_target_profiles():
    source = (ROOT / 'runtime/PaidSourceTargetProfiles.h').read_text(encoding='utf8')
    fields = re.findall(r'\b\w+\b', source.split('struct NativeProfile {', 1)[1].split('};', 1)[0].replace('std::uintptr_t', ''))
    # Only the first, explicitly named table; do not borrow similarly shaped
    # audit windows or later profile tables.
    table = source.split('constexpr NativeProfile Profiles[]={', 1)[1].split('\n};', 1)[0]
    rows = re.findall(r'\{([^{}]+)\}', table)
    if len(rows) != 3:
        raise ValueError('Expected exactly three paid-source native profiles')
    result = {}
    for branch, row in zip(BRANCHES, rows):
        values = [int(value.strip().rstrip('uU'), 0) for value in row.split(',')]
        if len(values) != len(fields):
            raise ValueError('Paid-source native field count changed')
        result[branch] = dict(zip(fields, values))
    return result


def quest_board_profiles():
    source = (ROOT / 'runtime/MajestyModManagerRuntime.cpp').read_text(encoding='utf8')
    fields = re.findall(r'\b(\w+);', source.split('struct QuestBoardBuildProfile {', 1)[1].split('};', 1)[0])
    result = {}
    for branch, label in zip(BRANCHES, ('kPublicQuestBoard', 'kBeta2QuestBoard', 'kGogQuestBoard')):
        values = initializer(source, label)
        if len(values) != len(fields):
            raise ValueError('Quest-board native field count changed')
        result[branch] = {field: int(value, 0) for field, value in zip(fields, values)}
    return result


def freestyle_profiles():
    source = re.sub(r'//[^\n]*', '', (ROOT / 'runtime/FreestyleCamRuntime.cpp').read_text(encoding='utf8'))
    fields = re.findall(r'\b(\w+)(?:\[\d+\])?;', source.split('struct FreestyleCamProfile {', 1)[1].split('};', 1)[0])
    result = {}
    for branch, label in zip(BRANCHES, ('kPublicFreestyleProfile', 'kBeta2FreestyleProfile', 'kGogFreestyleProfile')):
        values = initializer(source, label)
        if len(values) != len(fields):
            raise ValueError('Freestyle native profile field count changed')
        result[branch] = {field: int(value, 0) for field, value in zip(fields, values)
                          if re.fullmatch(r'0x[0-9a-fA-F]+|[0-9]+', value)}
    return result
