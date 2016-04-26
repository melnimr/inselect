#!/usr/bin/env python
"""Segment documents
"""
from __future__ import print_function

import argparse
import sys
import traceback

from pathlib import Path

# Import numpy here to prevent PyInstaller build from breaking
# TODO LH find a better solution
import numpy    # noqa

import inselect.lib.utils

from inselect.lib.document import InselectDocument
from inselect.lib.segment_document import SegmentDocument
from inselect.lib.utils import debug_print


# TODO Recursive option
# TODO Option to resegment documents with existing boxes

def segment(dir, sort_by_columns):
    dir = Path(dir)
    segment_doc = SegmentDocument(sort_by_columns)
    for p in dir.glob('*' + InselectDocument.EXTENSION):
        doc = InselectDocument.load(p)
        if not doc.items:
            print(u'Segmenting [{0}]'.format(p))
            try:
                debug_print(u'Will segment [{0}]'.format(p))
                doc, display_image = segment_doc.segment(doc)
                del display_image    # We don't use this
                doc.save()
            except KeyboardInterrupt:
                raise
            except Exception:
                print(u'Error segmenting [{0}]'.format(p))
                traceback.print_exc()
            else:
                print(u'Segmented [{0}]'.format(doc))
        else:
            print(u'Skipping [{0}] as it already contains items'.format(p))


def main(args):
    parser = argparse.ArgumentParser(description='Segments Inselect documents')
    parser.add_argument("dir", help='Directory containing Inselect documents')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument(
        '--sort-by-columns', action='store_true', default=False,
        help='Sort boxes columns; default is to sort boxes by rows')
    parser.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s ' + inselect.__version__
    )
    args = parser.parse_args(args)

    inselect.lib.utils.DEBUG_PRINT = args.debug

    segment(args.dir, args.sort_by_columns)


if __name__ == '__main__':
    main(sys.argv[1:])
