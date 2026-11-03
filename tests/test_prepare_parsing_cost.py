import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam.gpl import parse_gpl, _line_end
from majesty_cam.scoped_descriptions import inventory_records
from majesty_cam.compose import _parse_description_file_cached


class PrepareParsingTests(unittest.TestCase):
    def test_spans_keep_original_line_semantics(self):
        for newline in ('\n', '\r\n', '\r'):
            text = newline.join(['// prefix'] + [
                'function F%d()\ndeclare\nbegin\nend\n' % i
                for i in range(250)])
            result = parse_gpl(text)
            for item in result.items:
                span = item.span
                self.assertEqual(span.start_line, text.count('\n', 0, span.start)+1)
                self.assertEqual(span.end_line, text.count('\n', 0, max(span.start,span.end-1))+1)
                self.assertEqual(span.extract(text), item.text)
        for text, offset, end in [('abc\r\nrest',1,5),('abc\nrest',1,4),('abc\rrest',1,4),('abc',1,3)]:
            self.assertEqual(_line_end(text,offset),end)

    def test_xml_reuse_still_observes_same_size_same_timestamp_changes(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/'source.xml'
            first = '<Majesty><Description type="Unit" subType="Character" ID="TEST" Name="One"/></Majesty>'
            path.write_text(first)
            stamp = path.stat()
            inv = SimpleNamespace(descriptions=(path,))
            _parse_description_file_cached.cache_clear()
            from majesty_cam import compose
            with patch.object(compose,'parse_descriptions',wraps=compose.parse_descriptions) as parse:
                before = inventory_records(inv)
                self.assertEqual(inventory_records(inv),before)
                self.assertEqual(parse.call_count,1)
                path.write_text(first.replace('One','Two'))
                os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
                self.assertNotEqual(inventory_records(inv),before)
                self.assertEqual(parse.call_count,2)
