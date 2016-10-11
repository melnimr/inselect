#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys

import inselect


REQUIREMENTS = [
    #'cv2>=2.4.12,<3',
    'pathlib>=1.0.1,<1.1',
    'Pillow>=3.2.0,<3.4',
    'python-dateutil>=2.3,<=2.6',
    'pytz>=2015.7',
    'PyYAML>=3.10,<=3.12',
    'numpy>=1.10.1,<=1.11.1',
    'schematics>=1.1.1,<1.2',
    'scipy>=0.17.1,<=0.19',
    'scikit-learn>=0.17.1,<0.18',
    'unicodecsv>=0.14.1,<0.15',
]

SCRIPTS = ('export_metadata', 'ingest', 'read_barcodes', 'save_crops', 'segment')

setup_data = {
    'name': 'inselect',
    'version': inselect.__version__,
    'author': u'Lawrence Hudson, Alice Heaton, Pieter Holtzhausen, Stéfan van der Walt',
    'author_email': 'l.hudson@nhm.ac.uk',
    'maintainer': 'Lawrence Hudson',
    'maintainer_email': 'l.hudson@nhm.ac.uk',
    'url': 'https://github.com/NaturalHistoryMuseum/inselect/',
    'license': 'Modified BSD',
    'description': inselect.__doc__,
    'long_description': inselect.__doc__,
    'packages': [
        'inselect', 'inselect.gui', 'inselect.gui.plugins',
        'inselect.gui.views', 'inselect.gui.views.boxes', 'inselect.lib',
        'inselect.lib.templates', 'inselect.scripts',
    ],
    # 'package_data': {"": ['inselect/inselect.qss',]},
    # data_files = [('', ['libzbar64-0.dll', 'libiconv.dll'])],
    # 'package_data': {"": ['data/*',]},
    'include_package_data': True,
    'test_suite': 'inselect.tests',
    'scripts': ['inselect/scripts/{0}.py'.format(script) for script in SCRIPTS],
    'install_requires': REQUIREMENTS,
    'extras_require': {
        'GUI':  ['exifread>=2.1.2', 'humanize>=0.5.1', 'psutil>=4.0.0', 'PySide>=1.2.1'],
        'Barcodes': ['gouda>=0.1.6', 'ppydmtx>=0.7.4b1', 'zbar>=0.10'],
        'Inlite barcode reader': ['win32com>=220'],
        'Richer UI on Windows': ['win32com>=220'],
    },
    'entry_points': {
        'gui_scripts':
            ['inselect = inselect.app:main'],
        'console_scripts':
            ['{0} = inselect.scripts.{0}:main'.format(script) for script in SCRIPTS],
    },
    'win32': {
        'executables': [
            {
                'script': 'inselect.py',
                'targetName': 'inselect.exe',
                'icon': 'icons/inselect.ico',
                'base': 'Win32GUI',
                'shortcutName': 'Inselect',     # See http://stackoverflow.com/a/15736406
                'shortcutDir': 'ProgramMenuFolder'
            }
        ] + [
            {
                'script': 'inselect/scripts/{0}.py'.format(script),
                'targetName': '{0}.exe'.format(script),
                'icon': 'icons/inselect.ico',
                'base': 'Console'
            }
            for script in SCRIPTS
        ],
        # Strings in braces within 'include_files' tuples expanded in cx_setup
        'include_files': [
            ('{site_packages}/numpy', 'numpy'),
            ('{site_packages}/scipy', 'scipy'),
            ('{site_packages}/sklearn', 'sklearn'),
            ('{environment_root}/Library/bin/mkl_core.dll', 'mkl_core.dll'),
            ('{environment_root}/Library/bin/libiomp5md.dll', 'libiomp5md.dll'),
            ('{project_root}/inselect/inselect.qss', 'inselect.qss'),
        ],
        'extra_packages': ['win32com.gen_py'],
        'excludes': [
            'Tkinter', 'ttk', 'Tkconstants', 'tcl', '_ssl',
            'future.moves',    # Errors from urllib otherwise
            'PySide.QtNetwork',
        ]
    }
}


def setuptools_setup():
    """setuptools setup"""
    from setuptools import setup
    setup(**{k: v for k, v in setup_data.iteritems() if 'win32' != k})


def cx_setup():
    """cx_Freeze setup. Used for building Windows installers"""
    from cx_Freeze import setup, Executable
    from distutils.sysconfig import get_python_lib
    from pathlib import Path

    # Set paths to include files
    format_strings = {
        'site_packages': get_python_lib(),
        'environment_root': Path(sys.executable).parent,
        'project_root': Path(__file__).parent,
    }
    include_files = []
    for i in setup_data['win32']['include_files']:
        include_files.append((
            i[0].format(**format_strings),
            i[1]
        ))

    # Setup
    setup(
        name=setup_data['name'],
        version=setup_data['version'],
        options={
            'build_exe': {
                'packages': setup_data['packages'] + setup_data['win32']['extra_packages'],
                'excludes': setup_data['win32']['excludes'],
                'include_files': include_files,
                'include_msvcr': True,
                'optimize': 2,
            },
            'bdist_msi': {
                'upgrade_code': '{fe2ed61d-cd5e-45bb-9d16-146f725e522f}'
            }
        },
        executables=[Executable(**i) for i in setup_data['win32']['executables']]
    )


# User cx_Freeze to build Windows installers, and distutils otherwise.
if 'bdist_msi' in sys.argv:
    cx_setup()
else:
    setuptools_setup()
