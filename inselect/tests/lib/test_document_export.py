# -*- coding: UTF-8 -*-
import unittest

from itertools import izip, count
from pathlib import Path

import cv2
import numpy as np

from inselect.lib.document import InselectDocument
from inselect.lib.document_export import DocumentExport
from inselect.lib.unicode_csv import UnicodeDictReader

from inselect.tests.utils import temp_directory_with_files

TESTDATA = Path(__file__).parent.parent / 'test_data'


class TestDocumentExportNoTemplate(unittest.TestCase):
    def test_save_crops(self):
        "Cropped object images are written correctly"
        with temp_directory_with_files(TESTDATA / 'test_segment.inselect',
                                       TESTDATA / 'test_segment.png') as tempdir:
            doc = InselectDocument.load(tempdir / 'test_segment.inselect')

            crops_dir = DocumentExport().save_crops(doc)

            self.assertTrue(crops_dir.is_dir())
            self.assertEqual(crops_dir, doc.crops_dir)
            self.assertEqual(5, len(list(crops_dir.glob('*.png'))))

            # Check the contents of each file
            boxes = doc.scanned.from_normalised([i['rect'] for i in doc.items])
            for box, path in izip(boxes, sorted(crops_dir.glob('*.png'))):
                x0, y0, x1, y1 = box.coordinates
                self.assertTrue(np.all(doc.scanned.array[y0:y1, x0:x1] ==
                                       cv2.imread(str(path))))

    def test_csv_export(self):
        "CSV data are exported as expected"
        with temp_directory_with_files(TESTDATA / 'test_segment.inselect',
                                       TESTDATA / 'test_segment.png') as tempdir:
            doc = InselectDocument.load(tempdir / 'test_segment.inselect')

            csv_path = DocumentExport().export_csv(doc)
            self.assertEqual(csv_path, tempdir / 'test_segment.csv')

            # Check CSV contents
            with csv_path.open('rb') as f:
                res = UnicodeDictReader(f)
                for index, item, row in izip(count(), doc.items, res):
                    expected = item['fields']
                    expected.update({'Item': '{0}'.format(1+index),
                                     'Cropped_image_name': '{0:04}.png'.format(1+index),
                                    })
                    actual = {k: v for k,v in row.items() if v}
                    self.assertEqual(expected, actual)
        # Expect 4 rows
        self.assertEqual(index, 4)


if __name__=='__main__':
    unittest.main()
