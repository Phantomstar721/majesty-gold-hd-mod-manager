"""Manager-generated provenance for the exact-profile attack observer.

Input BCDs are the actual compiler results and native baseline archives. No
package may assert its own digest, native address, or protected-definition list.
This proof does not certify when the game loads a file; the native completion
gate independently observes that and refuses unexpected or overlapping loads.
"""
from dataclasses import dataclass
import hashlib
import struct

from .bcd import definition_keys
from .gpl import DefinitionKind

RELATIVE_PATH = "DataMX/majesty_mod_manager_attack_observation.bin"
BASELINES = ("Data/Bytecode.bcd", "DataMX/MX_Compatibility.bcd",
             "DataMX/MX_Build.bcd", "DataMX/MX_Data.bcd",
             "DataMX/MX_Decision.bcd", "DataMX/MX_Task.bcd")
BASELINE_SHA256 = (
    "79b4815df03f0132dd61005082651288dfbdda0ef51931d566c4665015d8a8bd",
    "a5f4f612406506316e2b409b35f4e7014dbca4291143f8c888f040d5c15f6f91",
    "5ac5227a73d9859f96ad686f1649c3ff346e69269b3d77c9be6f168c1202c37b",
    "1425c6cf51faddd655e03623544d055c5c6d3581df8ce026b2a4ef4b57d2b817",
    "3922797215f49906962b92dcd5411f707a9b0d7db31b0b9bc77e945d11353b7c",
    "c9ff9d26b896e5853ba64873ec812f62bac45daddaf8f4700b0201f4cbdcc5f0",
)
# Complete stock archive bundle, not interchangeable per-file alternatives.
# See docs/dawnfall-baseline-parity.md for the instruction/symbol comparison.
PUBLIC_BASELINE_SHA256 = (
    "024e1b872e4b21d79677bca811ebb11a09a4434049c03d2c2f9d758fa04ee58f",
    BASELINE_SHA256[1],
    "461f47f4e8ec83301be81f524013b1603a8251ca86a7f2ce13ddc192ebb49494",
    "0467f3cc06c676bdf7e77dece17673c2a651da66450b7dd3eb5acde066e26513",
    BASELINE_SHA256[4],
    "308294eb59e05d620dde6b4f2691d8c312d10f7fd4dab76b3dfecd0cbc1b987f",
)
MAX_FILES = 256
# Stock combat definitions eligible for protection when actually composed.
# Declared native aliases and directly required callbacks are also protected.
# Unrelated baseline quest entry points do not own this observation boundary.
STOCK_COMBAT_NAMES = frozenset(("make_attack", "hit", "gettohit", "gettoavoid",
    "notvalid", "notvalid_attacker", "damage_dispatch", "attack_end", "exp_value",
    "attack_object", "rogues_guild_birth"))
_FIELDS = ("feature_key", "api_prefix", "actor", "action", "projectile", "release_callback_symbol")


@dataclass(frozen=True)
class Proof:
    feature: object
    # First six archives are native baseline IDs; seventh is emitted output.
    # Remaining records may load anywhere but cannot override protected names.
    digests: tuple[bytes, ...]
    scoped: bool = False
    protected_names: tuple[str, ...] = ()


def audited_baseline(digests):
    """Accept a complete reviewed bundle, never per-file alternatives."""
    return tuple(digests) in (BASELINE_SHA256, PUBLIC_BASELINE_SHA256)


def validate_output(proof, targets):
    """Shared final validation of stock provenance and ordered compiler bytes."""
    targets = tuple(targets)
    count = 3 if proof.scoped else 1
    if not audited_baseline(d.hex() for d in proof.digests[:6]):
        raise ValueError("observer proof baseline is not a complete audited stock bundle")
    if (len(targets) != count or
            tuple(hashlib.sha256(data).digest() for data in targets) != proof.digests[6:6+count]):
        raise ValueError("observer proof does not match its actual ordered compiled output")


def build_proof(bindings, baseline_bytes, emitted_bytes, optional_bytes=(), *, extra_protected_names=(), shared_only=False, required_functions=(), protected_functions=()):
    bindings = tuple(bindings)
    if bindings or not shared_only:
        raise ValueError("release proof supports shared projectile interception only")
    feature = None
    baseline_bytes = tuple(baseline_bytes)
    if len(baseline_bytes) != len(BASELINES):
        raise ValueError("attack observation requires all six native baseline archives")
    # Reject malformed/opaque archives, even if their digest would be stable.
    aliases = set()
    aliases |= {n.casefold() for n in extra_protected_names}
    for data in baseline_bytes:
        if aliases.intersection(name for _,name in definition_keys(data)):
            raise ValueError("baseline BCD defines a declared native alias")
    outputs = (emitted_bytes,) if isinstance(emitted_bytes,bytes) else tuple(emitted_bytes)
    if len(outputs) not in (1,3):
        raise ValueError("observer proof requires Any alone or Any plus both dataset patches")
    keys = tuple(definition_keys(data) for data in outputs)
    output_keys = frozenset().union(*keys)
    needed = {(DefinitionKind.FUNCTION, n.casefold()) for n in required_functions}
    effective_keys = (keys[0],) if len(keys)==1 else (keys[0]|keys[1], keys[0]|keys[2])
    if any(not needed <= effective for effective in effective_keys):
        raise ValueError("compiled observer output is missing its effective callbacks")
    aliases = set()
    if any(name in aliases for _, name in output_keys):
        raise ValueError("compiled output defines a native observer alias")
    # Protect the observation contract, not every unrelated definition that
    # happens to share a compiled file with it (quest constants, hero trees...).
    emitted_names = {name for _,name in output_keys}
    protected_names = (STOCK_COMBAT_NAMES & emitted_names) | aliases | {n.casefold() for n in extra_protected_names}
    protected_names |= {n.casefold() for n in required_functions}
    protected_names |= {n.casefold() for n in protected_functions}
    payloads = [*baseline_bytes, *outputs]
    for data in optional_bytes:
        keys = definition_keys(data)
        if protected_names.intersection(name for _, name in keys):
            raise ValueError("another BCD overrides a protected composed definition or native alias")
        if data not in payloads:
            payloads.append(data)
    proof = Proof(feature, tuple(hashlib.sha256(data).digest() for data in payloads),len(outputs)==3,
                  tuple(sorted(protected_names)))
    encode(proof)  # Apply the exact native wire bounds at the generating boundary.
    return proof


def encode(proof):
    if proof.feature is not None:
        raise ValueError("private actor proofs are excluded from this release")
    value = None
    if (not (9 if proof.scoped else 7) <= len(proof.digests) <= MAX_FILES or
            any(not isinstance(d, bytes) or len(d) != 32 for d in proof.digests) or
            len(set(proof.digests)) != len(proof.digests)):
        raise ValueError("observer proof requires 7..256 distinct SHA256 records")
    version = (2 if proof.scoped else 1) + (0 if value else 2)
    if proof.protected_names:
        version += 4
    chunks = [struct.pack("<4sII", b"MMOB", version, len(proof.digests))]
    for field in (_FIELDS if value else ()):
        text = value[field].encode("ascii")
        chunks.extend((struct.pack("<I", len(text)), text))
    chunks.extend(proof.digests)
    if proof.protected_names:
        if tuple(sorted(set(proof.protected_names))) != proof.protected_names or len(proof.protected_names)>4096:
            raise ValueError("invalid observer protected definitions")
        chunks.append(struct.pack('<I',len(proof.protected_names)))
        import re
        for name in proof.protected_names:
            if not re.fullmatch(r'#[a-z_][a-z_0-9]*|[a-z_][a-z_0-9]*',name) or len(name)>128:
                raise ValueError("invalid observer protected definition")
            raw=name.encode('ascii'); chunks.extend((struct.pack('<I',len(raw)),raw))
    return b"".join(chunks)


def decode(data):
    if not isinstance(data, bytes) or not 12 <= len(data) <= 1048576:
        raise ValueError("observer proof size is invalid")
    magic, version, count = struct.unpack_from("<4sII", data)
    if magic != b"MMOB" or version not in (3,4,7,8) or not (9 if version%2==0 else 7) <= count <= MAX_FILES:
        raise ValueError("observer proof header is invalid")
    value = {"type": "stock.attack-projectile-observation.v1"}
    pos = 12
    base_version=(version-1)%4+1
    for field in (_FIELDS if base_version<3 else ()):
        if pos + 4 > len(data):
            raise ValueError("observer proof name is truncated")
        size, = struct.unpack_from("<I", data, pos)
        pos += 4
        if not 1 <= size <= 64 or pos + size > len(data):
            raise ValueError("observer proof name size is invalid")
        try:
            value[field] = data[pos:pos+size].decode("ascii")
        except UnicodeError as exc:
            raise ValueError("observer proof names must be ASCII") from exc
        pos += size
    if len(data) - pos < count * 32:
        raise ValueError("observer proof digest table size is invalid")
    digests=tuple(data[i:i+32] for i in range(pos,pos+count*32,32)); pos+=count*32
    names=[]
    if version>4:
        if pos+4>len(data): raise ValueError('truncated protected definitions')
        total,=struct.unpack_from('<I',data,pos);pos+=4
        if not 1<=total<=4096: raise ValueError('invalid protected definition count')
        for _ in range(total):
            if pos+4>len(data): raise ValueError('truncated protected definition')
            size,=struct.unpack_from('<I',data,pos);pos+=4
            if not 1<=size<=128 or pos+size>len(data): raise ValueError('invalid protected definition size')
            try: names.append(data[pos:pos+size].decode('ascii'))
            except UnicodeError as exc: raise ValueError('invalid protected definition') from exc
            pos+=size
    if pos!=len(data): raise ValueError('trailing observer proof data')
    result = Proof(None,digests,base_version in (2,4),tuple(names))
    if encode(result) != data:
        raise ValueError("observer proof is not canonical")
    return result


def from_composed_output(game_path, bindings, emitted_bytes, *, extra_protected_names=(), shared_only=False, required_functions=(), protected_functions=()):
    """Read-only handoff after compilation; never composes a Manager profile."""
    from pathlib import Path
    root = Path(game_path)
    baseline = tuple((root / path).read_bytes() for path in BASELINES)
    if not audited_baseline(hashlib.sha256(data).hexdigest() for data in baseline):
        raise ValueError("attack observation native baseline archives differ from the audited profile")
    options = dict(extra_protected_names=extra_protected_names, shared_only=shared_only, required_functions=required_functions, protected_functions=protected_functions)
    proof = build_proof(bindings, baseline, emitted_bytes, **options)
    optional = []
    required_paths = {(root / path).resolve() for path in BASELINES}
    for directory in (root / "Data", root / "DataMX"):
        for path in sorted(directory.glob("*.bcd"), key=lambda p: str(p).casefold()):
            if path.resolve() in required_paths:
                continue
            data = path.read_bytes()
            # Unselected quest files are not evidence requirements. Only admit
            # non-overriding known files; loading any excluded file is Unknown.
            try:
                build_proof(bindings, baseline, emitted_bytes, (data,), **options)
            except ValueError:
                continue
            optional.append(data)
    return build_proof(bindings, baseline, emitted_bytes, optional, **options)
