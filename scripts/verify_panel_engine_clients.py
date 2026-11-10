"""Recover the SDK reset client using whole-body bytes and verified callees.

No game process is opened. A match is accepted only when the complete straight-
line body has identical instructions and its three calls resolve to the exact
already guarded stock providers. No generic offset delta or prefix admission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from majesty_cam.manager.qol_service import detect_majesty_branch


def verify(fixtures):
    import pefile
    header = (ROOT / "runtime/BooleanRuntimeProfiles.h").read_text(encoding="utf8")
    by_name = {}
    for address, size, values, name in re.findall(
            r"\{(0x[0-9a-f]+),(\d+),\{([^}]+)\}\}, // (\w+)", header):
        digest = bytes(int(v.strip(), 16) for v in values.split(","))
        assert len(digest) == 32
        by_name.setdefault(name, []).append((int(address,16), int(size), digest.hex()))
    # Exact public provider-client body established in the SDK source-guided
    # trace. All branch/callee instructions lie within this complete 31 bytes.
    public = pefile.PE(data=fixtures["public"].read_bytes())
    template = public.get_data(0x562ea0 - public.OPTIONAL_HEADER.ImageBase, 31)
    assert hashlib.sha256(template).hexdigest() == "360e566d6b1ad2522800dfdaaf1d38cc1c3430526bd62f18b515d48782a045bd"
    assert template[:6] == bytes.fromhex("568d71088bce") and template[-2:] == bytes.fromhex("5ec3")
    calls = (6, 15, 24)
    assert all(template[offset] == 0xe8 for offset in calls)
    parts, start = [], 0
    for offset in calls:
        parts.append(re.escape(template[start:offset+1]))
        parts.append(b"[\\s\\S]{4}")
        start = offset + 5
    parts.append(re.escape(template[start:]))
    pattern = re.compile(b"".join(parts))
    results = {}
    for index, (branch, path) in enumerate(fixtures.items()):
        data = path.read_bytes()
        detected = detect_majesty_branch(path)
        assert detected and (detected.key == branch or branch == "gog" and detected.key.startswith("gog"))
        pe = pefile.PE(data=data)
        base = pe.OPTIONAL_HEADER.ImageBase
        providers = [by_name[name][index] for name in ("FrameDrain", "AppendInteger", "RebuildSlots")]
        for address, size, digest in providers:
            assert hashlib.sha256(pe.get_data(address-base,size)).hexdigest() == digest
        matches = []
        for section in pe.sections:
            if not section.Characteristics & 0x20000000:
                continue
            payload = section.get_data()
            for match in pattern.finditer(payload):
                address = base + section.VirtualAddress + match.start()
                body = match.group()
                destinations = [address+offset+5+struct.unpack_from('<i',body,offset+1)[0] for offset in calls]
                if destinations == [row[0] for row in providers]:
                    matches.append((address, body))
        assert len(matches) == 1, (branch, "reset-client match count", len(matches))
        address, body = matches[0]
        results[branch] = {"va":address,"size":len(body),"sha256":hashlib.sha256(body).hexdigest(),
            "fixtureSha256":hashlib.sha256(data).hexdigest(),
            "providers":[{"va":va,"size":size,"sha256":digest} for va,size,digest in providers]}
    return {"schema":1,"contract":"we1.gpl-evaluator-reset.v1", "normalReturnOnly":True,
        "source":"SDK we_engine.cpp GDH_RESET; Manager BooleanRuntimeProfiles.h providers",
        "layout":"this+8 argument frame; reseed integer zero; rebuild slots at frame+0x1c",
        "profiles":results}


def verify_integer_clients(fixtures):
    import pefile
    header = (ROOT / "runtime/BooleanRuntimeProfiles.h").read_text(encoding="utf8")
    providers = {}
    for address, size, values, name in re.findall(r"\{(0x[0-9a-f]+),(\d+),\{([^}]+)\}\}, // (\w+)", header):
        providers.setdefault(name, []).append((int(address,16), int(size),
            bytes(int(v.strip(),16) for v in values.split(',')).hex()))
    public = pefile.PE(data=fixtures['public'].read_bytes())
    contracts = (
        ('appendInteger',0x562c60,8,'dedcbd26ddd887c11278b5964809319bd5324188b2ade20282fc1f38e850677b',3,'AppendInteger',0xe9),
        ('returnInteger',0x563520,22,'7edea360dc7ab6760001e93ec9cf9832d72027800a2717a1095f950cf83ec987',5,'ResultAt',0xe8),
    )
    result = {}
    for name, public_address, size, digest, offset, provider, opcode in contracts:
        original = public.get_data(public_address-public.OPTIONAL_HEADER.ImageBase,size)
        assert hashlib.sha256(original).hexdigest() == digest and original[offset] == opcode
        pattern = re.compile(re.escape(original[:offset+1])+b'[\\s\\S]{4}'+re.escape(original[offset+5:]))
        profiles = {}
        for index, (branch,path) in enumerate(fixtures.items()):
            raw = path.read_bytes()
            pe = pefile.PE(data=raw); base=pe.OPTIONAL_HEADER.ImageBase
            address, length, provider_hash = providers[provider][index]
            assert hashlib.sha256(pe.get_data(address-base,length)).hexdigest() == provider_hash
            found=[]
            for section in pe.sections:
                if section.Characteristics & 0x20000000:
                    for match in pattern.finditer(section.get_data()):
                        va=base+section.VirtualAddress+match.start()
                        body=match.group()
                        target=va+offset+5+struct.unpack_from('<i',body,offset+1)[0]
                        if target==address:found.append((va,body))
            assert len(found)==1,(branch,name,len(found))
            va,body=found[0]
            profiles[branch]={'va':va,'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),
                'provider':{'va':address,'size':length,'sha256':provider_hash},
                'fixtureSha256':hashlib.sha256(raw).hexdigest()}
        result[name]={'profiles':profiles,'normalReturnOnly':True,
            'contract':('this+8 tail request to verified integer append' if name=='appendInteger'
                        else 'result slot0 at this+0x24, preserve native virtual integer accessor at +0x28')}
    return result


if __name__ == "__main__":
    import os
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    fixtures={name:Path(os.environ["MAJESTY_"+name.upper()+"_EXE"]) for name in ("public","beta2","gog")}
    result=verify(fixtures)
    result['relatedClients']=verify_integer_clients(fixtures)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print("Reset client profiles: "+", ".join(name+" "+hex(row['va']) for name,row in result['profiles'].items()))
