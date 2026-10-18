"""Offline, read-only three-image verification of stock inventory text consumers.

No game process is opened. Addresses are discovered from instruction signatures,
then the complete selected bodies are compared, retaining branch destinations,
registers, field offsets and non-address literals.
"""
import hashlib
import json
from pathlib import Path
import struct
import capstone
import pefile

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    "public": (Path(r"C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/MajestyHD.exe"), "255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4"),
    "beta2": (ROOT / "majesty-gold-hd-mod-manager-gog-support/local/fixtures/beta2/MajestyHD.exe", "05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82"),
    "gog": (ROOT / "majesty-gold-hd-mod-manager-gog-support/local/fixtures/gog-pristine/MajestyHD.exe", "65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792"),
}
SLICES = {"item_text": (0x51e920, 0x95), "items_list": (0x4a2e30, 0x1a1),
          "menu_append": (0x4b4750, 0x1e)}
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True


def decoded(pe, va, size):
    return list(md.disasm(pe.get_data(va-pe.OPTIONAL_HEADER.ImageBase, size), va))


def normalized(pe, va, size):
    base = pe.OPTIONAL_HEADER.ImageBase
    end = base + pe.OPTIONAL_HEADER.SizeOfImage
    result = []
    for ins in decoded(pe, va, size):
        operands = []
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_REG:
                operands.append(("reg", ins.reg_name(op.reg)))
            elif op.type == capstone.x86.X86_OP_IMM:
                v = op.imm
                if ins.group(capstone.CS_GRP_JUMP) and va <= v < va+size:
                    v = ("local", v-va)
                elif base <= v < end:
                    v = "image-address"
                operands.append(("imm", v))
            else:
                m = op.mem
                operands.append(("mem", ins.reg_name(m.base), ins.reg_name(m.index), m.scale,
                                 "image-address" if base <= m.disp < end else m.disp))
        result.append((ins.address-va, ins.mnemonic, operands))
    return result


def main():
    images = {}
    for name, (path, expected) in PROFILES.items():
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"unsupported {name} executable: {actual}")
        images[name] = pefile.PE(data=data)
    public = images["public"]
    report = {}
    for label, (reference, size) in SLICES.items():
        expected = normalized(public, reference, size)
        # Prefix stops before the first relocation/absolute operand.
        prefix_size = 18 if label == "item_text" else 3 if label == "items_list" else 9
        prefix = public.get_data(reference-0x400000, prefix_size)
        report[label] = {}
        for name, pe in images.items():
            comparison = expected
            if name == "gog" and label == "items_list":
                # GOG's three list message dispatches use vtable +0x74 rather
                # than Steam +0x68. Retain every other operand and instruction.
                comparison = [(offset, mnemonic,
                    [("reg", "eax"), ("mem", "edx", None, 1, 0x74)]
                    if offset in (81, 106, 127) else operands)
                    for offset, mnemonic, operands in expected]
            candidates = []
            for section in pe.sections:
                if not section.Characteristics & 0x20000000:
                    continue
                data = section.get_data()
                start = 0
                while (offset := data.find(prefix, start)) >= 0:
                    start = offset+1
                    if label == "items_list" and data[offset+7:offset+16] != public.get_data(reference-0x400000+7, 9):
                        continue
                    va = pe.OPTIONAL_HEADER.ImageBase+section.VirtualAddress+offset
                    if normalized(pe, va, size) == comparison:
                        candidates.append(va)
            if len(candidates) != 1:
                raise ValueError(f"{name}/{label}: expected one complete-body match, got {candidates}")
            va = candidates[0]
            body = pe.get_data(va-pe.OPTIONAL_HEADER.ImageBase, size)
            report[label][name] = {"va": hex(va), "size": size, "sha256": hashlib.sha256(body).hexdigest(),
                                  "calls": [i.op_str for i in decoded(pe, va, size) if i.mnemonic == "call"]}
    # Resolve QITM acquisition independently from each image, not from a delta.
    report["qitm"] = {}
    for name, pe in images.items():
        hits = []
        for section in pe.sections:
            if section.Characteristics & 0x20000000:
                data = section.get_data()
                start = 0
                while (off := data.find(b"\x68QITM\x6a\x00\xe8", start)) >= 0:
                    start = off+1
                    va = pe.OPTIONAL_HEADER.ImageBase+section.VirtualAddress+off
                    hits.append(hex(va))
        if len(hits) != 1:
            raise ValueError(f"{name}: ambiguous QITM acquisition {hits}")
        report["qitm"][name] = hits[0]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
