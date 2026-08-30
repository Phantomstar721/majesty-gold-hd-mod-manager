from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.capabilities import SUPPORTED_RUNTIME_CAPABILITIES
from majesty_cam.runtime_capabilities import (
    decode_runtime_capability_manifest,
    encode_runtime_capability_manifest,
    write_runtime_capability_manifest,
)


class RuntimeCapabilityManifestTests(unittest.TestCase):
    def test_supported_capabilities_round_trip_deterministically(self):
        capabilities = tuple(SUPPORTED_RUNTIME_CAPABILITIES)
        forward = encode_runtime_capability_manifest(capabilities)
        reverse = encode_runtime_capability_manifest(tuple(reversed(capabilities)))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            decode_runtime_capability_manifest(forward),
            tuple(sorted(capabilities)),
        )

    def test_empty_generic_and_private_name_profiles_are_distinct(self):
        generic = (
            "expanded-building-slots.cg-prefix",
            "freestyle-cam-rebind.v1",
            "generic-visitor-lists.v1",
        )
        alchemist = (
            *generic,
            "alchemist.ap78-private-oil-rows",
            "alchemist.cgbrewing-secondary-controller",
            "alchemist.nm18-name-generator",
        )
        phantom = (*generic, "phantom.nm19-name-generator")
        self.assertEqual(decode_runtime_capability_manifest(
            encode_runtime_capability_manifest(())
        ), ())
        self.assertEqual(
            decode_runtime_capability_manifest(
                encode_runtime_capability_manifest(generic)
            ),
            tuple(sorted(generic)),
        )
        self.assertEqual(
            decode_runtime_capability_manifest(
                encode_runtime_capability_manifest(alchemist)
            ),
            tuple(sorted(alchemist)),
        )
        self.assertEqual(
            decode_runtime_capability_manifest(
                encode_runtime_capability_manifest(phantom)
            ),
            tuple(sorted(phantom)),
        )

    def test_decoder_rejects_truncation_duplicates_order_and_trailing_bytes(self):
        payload = encode_runtime_capability_manifest((
            "example.alpha.v1",
            "example.beta.v1",
        ))
        for size in range(0, len(payload)):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    decode_runtime_capability_manifest(payload[:size])
        with self.assertRaisesRegex(ValueError, "trailing"):
            decode_runtime_capability_manifest(payload + b"x")

        alpha = b"example.alpha.v1"
        duplicate = (
            struct.pack("<4sII", b"MMCP", 1, 2)
            + struct.pack("<I", len(alpha)) + alpha
            + struct.pack("<I", len(alpha)) + alpha
        )
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            decode_runtime_capability_manifest(duplicate)

    def test_encoder_rejects_invalid_and_duplicate_names(self):
        invalid = (
            "UPPER.case",
            "single",
            ".leading.segment",
            "trailing.segment.",
            "space.bad name",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    encode_runtime_capability_manifest((value,))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            encode_runtime_capability_manifest(("example.v1", "example.v1"))

    def test_atomic_writer_replaces_with_canonical_payload(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manager" / "capabilities.mmcp"
            path.parent.mkdir()
            path.write_bytes(b"stale")
            canonical = write_runtime_capability_manifest(
                path, ("example.zeta.v1", "example.alpha.v1")
            )
            self.assertEqual(
                canonical,
                ("example.alpha.v1", "example.zeta.v1"),
            )
            self.assertEqual(
                decode_runtime_capability_manifest(path.read_bytes()), canonical
            )


if __name__ == "__main__":
    unittest.main()
