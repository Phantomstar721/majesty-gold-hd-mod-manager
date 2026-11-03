"""Exact-image movement/cast ABI evidence; native execution is not implied."""
import hashlib
import os
import unittest
from pathlib import Path

from test_occupant_runtime_profiles import PeImage


class DawnfallNativeProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("MAJESTY_BETA2_EXE")
        if not path:
            raise unittest.SkipTest("MAJESTY_BETA2_EXE not supplied")
        cls.image = PeImage(path)
        # Same beta2 layout; retain every consumed-byte/call assertion below.
        from majesty_cam.manager.qol_service import detect_majesty_branch, BETA2_BRANCH
        branch = detect_majesty_branch(Path(path))
        if branch is None or branch.key != BETA2_BRANCH.key:
            raise AssertionError("unreviewed movement profile")

    def at(self, va, expected):
        expected = bytes.fromhex(expected)
        self.assertEqual(self.image.read(va-self.image.base, len(expected)), expected)

    def call(self, va, target):
        self.assertEqual(self.image.target(va-self.image.base)+self.image.base, target)

    def test_stock_path_query_and_original_endpoint_comparison(self):
        self.at(0x5D63C0, "6880395d00")
        self.call(0x5D3B81, 0x5DA530)
        self.call(0x61C3EA, 0x61C100)
        self.at(0x61C3F3, "3b500c")
        self.at(0x61C3FC, "3b4810")
        self.at(0x61C40E, "880a")
        self.call(0x61C08E, 0x61B6A0)
        self.call(0x61B6D0, 0x5E1C30)

    def test_full_footprint_dispatch_and_point_teleport_bypass(self):
        self.at(0x5E1C61, "bbc03e6200")
        self.at(0x5E1C72, "8b068b90c0000000558bceffd2")
        self.call(0x5E1C9F, 0x5E1B60)
        self.call(0x5E1CC3, 0x5E1A90)
        self.call(0x4332C1, 0x5DA580)
        self.at(0x4332FD, "894c242089742424ebd6")
        self.at(0x4332DD, "8b038b90700100008bcbffd2")
        self.call(0x4332F0, 0x5D7520)

    def test_cancel_channels_are_indirect_before_relocation(self):
        self.at(0x5DEF25, "8b90740100006a01ffd2")
        self.at(0x5DEF31, "8b90740100006a008bceffd2")
        self.at(0x5DEF3F, "8b90740100006a028bceffd2")
        self.at(0x5DEF06, "8b806c01000052ffd0")
        self.at(0x5DEF13, "8b108bc88b4238ffd0")

    def test_death_notification_precedes_script_execution(self):
        # These three concrete classes share the HP notification, but this
        # does not assert that every direct native dead-bit writer uses it.
        for table in (0x7539E4, 0x75414C, 0x7530C4):
            self.at(table + 0x124, "50994400")
        self.at(0x5DE4F3, "8b55008b922401000050518bcdffd2")
        self.at(0x4499E1, "81fb415055007435")
        self.at(0x449A31, "83ff017dd2")
        self.call(0x449AC6, 0x5798F0)

    def test_relocation_has_notifications_inside_the_final_call(self):
        for table in (0x7539E4, 0x75414C, 0x7530C4):
            self.at(table + 0xB8, "40be5d00")
            self.at(table + 0xBC, "70765d00")
        self.at(0x5D7479, "8b068b90b8000000ffd28b068b90bc0000008bceffd2")
        # The +BC body walks linked units and calls their +B8, too.
        self.at(0x5D774D, "8b0e8b018b90b8000000ffd2")
        self.at(0x5DBE40, "a1d43f7e0085c0740d8b401c8b10518bc88b4208ffd0c3")
        self.at(0x5D6E27, "56ff15b87c7d00")
        self.at(0x7D7CB8, "a0725d00")

    def test_bitmap_stride_bit_order_and_rectangle_exclusive_limits(self):
        self.at(0x5E1B90, "8b6f080fafeb8bc69983e20703c28b5714c1f8038bce03e881e10700008079054983c9f841b801000000d3e084042a7440")
        self.at(0x5E1B16, "3bf97d3a8b6c24348bff3bf27d2b")

    def test_cast_submission_and_callback_abis(self):
        self.at(0x5DF310,"558b6c240c57")
        self.at(0x5DF384,"8bc55dc20800") # returns the submitted order, RET8
        self.at(0x5DF7B0,"8b44240c535556578b7c24148baf94000000")
        self.at(0x5DF7FF,"c20c00")
        self.at(0x60C093,"8b465c") # action ID, not a descriptor pointer
        self.at(0x60C0BD,"8b4660") # fixed captured target
        self.call(0x60C165,0x5DAE90)
        self.at(0x5DAEC6,"c21000")
        self.at(0x5938C1,"8b4e088d461050")
        self.call(0x5938C8,0x590E40)
        self.at(0x5D3340,"538b5c2408")
        self.at(0x592F40,"a1a8297e00")
        self.at(0x566130,"6aff6858017200")

    def test_checked_write_replays_whole_instructions(self):
        self.at(0x5D748F,"8b44241c8b08")
        self.at(0x5D7495,"894e588b5004")
        self.at(0x5D70E6,"8b868400000085c07476")
        self.at(0x5D7166,"8b4e588b44241489088b565c895004")
        self.at(0x5D7255,"c1fa0bc1f80b")

    def test_direct_death_and_identity_invalidation_entries(self):
        self.at(0x4DFD70,"83497410c3")
        self.at(0x4DFDD0,"837c241402")
        self.at(0x4DFDEC,"834e7410")
        self.at(0x60CD40,"83ec18837c242c02")
        self.at(0x60CD54,"834e7410")
        self.at(0x622850,"83ec0c568b742414")
        self.at(0x622864,"834e7410")
        self.at(0x4494C0,"83ec0c568bf1")
        self.at(0x44955E,"c20800")
        self.at(0x5CF320,"8b442404398180000000")
        self.at(0x51AE30,"568bd18b4c2408")
        self.at(0x5DBA10,"8b4174a804")

    def test_loaded_catalog_and_team_representation(self):
        self.at(0x5C3010,"8b432c8b28")
        self.at(0x5C304D,"8b75108b4e0c")
        self.call(0x5C305E,0x63B150)
        self.call(0x5C306B,0x40BBF0) # native tree iterator, not linked-list next
        self.at(0x51AE0E,"d3e28514867508")
        self.at(0x51AE15,"4083f8087cf5")
        self.at(0x63A262,"c20400")
        self.at(0x581C63,"c20400")

    def test_refusal_keeps_post_notifications_without_coordinate_stores(self):
        self.call(0x5D74AB,0x5D70E0)
        self.at(0x5D74D2,"8b168b929c000000")
        self.at(0x5D74F5,"8b068b90b80000008bceffd2")
        self.at(0x5D7501,"8b068b90bc0000008bceffd2")
        self.at(0x5D750D,"5e83c414c20400")
        self.at(0x5DF3D0,"8b44240489413cc20400")
        self.at(0x593119,"8b4808")
        self.call(0x593121,0x581C10)
        self.at(0x5D3E77,"6a00508b450050")
        self.call(0x5D3E7E,0x5D1990)
