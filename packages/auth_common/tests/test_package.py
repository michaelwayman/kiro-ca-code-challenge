"""Package-level guarantees: version metadata, and a core that never imports Django (Req 8.3)."""

import subprocess
import sys

import auth_common


def test_version_matches_package_metadata() -> None:
    assert auth_common.__version__ == "0.0.1"


def test_core_imports_without_django() -> None:
    # Setting sys.modules["django"] = None makes any `import django` raise
    # ImportError, so this proves the core never imports Django, even in an
    # environment where Django happens to be installed (the dev group installs
    # django-stubs, which depends on Django).
    code = (
        "import sys\n"
        "sys.modules['django'] = None\n"
        "sys.modules['rest_framework'] = None\n"
        "import auth_common\n"
        "print(auth_common.__version__)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.0.1"
