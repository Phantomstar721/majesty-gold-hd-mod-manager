"""Locate existing evidence for SDK bindings; never infer or admit a port."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def audit(inventory):
    candidates = {}
    for folder in ("runtime", "docs"):
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file() or path.suffix not in (".h", ".cpp", ".inl", ".md"):
                continue
            for number, line in enumerate(path.read_text(encoding="utf8", errors="replace").splitlines(), 1):
                for match in re.finditer(r"0x([0-9a-fA-F]{5,8})\b", line):
                    address = int(match[1], 16)
                    kind = "VA literal" if address >= 0x400000 else "possible RVA literal"
                    if address < 0x400000:
                        address += 0x400000
                    candidates.setdefault(address, []).append({"path": str(path.relative_to(ROOT)),
                                                               "line": number, "kind": kind})
    result = {}
    for component, data in inventory.items():
        rows = []
        for binding in data.get("macros", ()):
            if binding.get("category") != "native-function":
                continue
            matches = []
            for address in binding.get("hex_values", ()):
                matches.extend(candidates.get(int(address, 16), ()))
            rows.append({"name": binding["name"], "publicSourceLine": binding["line"],
                         "publicSourceAddresses": binding.get("hex_values", ()),
                         "existingEvidenceCandidates": matches,
                         "portVerified": False})
        result[component] = {"sdkSourceSha256": data["sha256"], "bindings": rows}
    return {"schema": 1, "kind": "source-reference inventory, not native verification",
            "components": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    raw = args.inventory.read_bytes()
    result = audit(json.loads(raw))
    result["inventorySha256"] = hashlib.sha256(raw).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    for component, data in result["components"].items():
        missing = [row["name"] for row in data["bindings"] if not row["existingEvidenceCandidates"]]
        print(component + " source-reference gaps: " + ", ".join(missing))


if __name__ == "__main__":
    main()
