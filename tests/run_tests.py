import os
import sys
import unittest
from pkgutil import extend_path

import freecad

tests_directory = os.path.dirname(__file__)
addon_directory = os.path.dirname(tests_directory)
sys.path.insert(0, tests_directory)
sys.path.insert(0, addon_directory)

freecad.__path__ = extend_path(freecad.__path__, freecad.__name__)
os.environ["AUTOBODYEXPORT_PARAMETER_PATH"] = (
    "User parameter:BaseApp/Preferences/Mod/AutoBodyExportTests"
)

suite = unittest.defaultTestLoader.loadTestsFromName("test_core")
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
