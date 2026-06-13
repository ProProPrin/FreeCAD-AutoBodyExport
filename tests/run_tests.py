import os
import sys
import unittest
from pkgutil import extend_path

import freecad

tests_directory = os.path.dirname(__file__)
addon_directory = os.path.dirname(tests_directory)
sys.path.insert(0, tests_directory)
sys.path.insert(0, addon_directory)

repository_freecad_path = os.path.join(addon_directory, "freecad")
freecad.__path__ = [
    repository_freecad_path,
    *[
        path
        for path in extend_path(freecad.__path__, freecad.__name__)
        if os.path.normcase(os.path.abspath(path))
        != os.path.normcase(os.path.abspath(repository_freecad_path))
    ],
]
os.environ["AUTOBODYEXPORT_PARAMETER_PATH"] = (
    "User parameter:BaseApp/Preferences/Mod/AutoBodyExportTests"
)

suite = unittest.defaultTestLoader.loadTestsFromNames(["test_core", "test_i18n"])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
