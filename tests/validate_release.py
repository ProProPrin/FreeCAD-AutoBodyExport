"""Validate files required for a public Auto Body Export release."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAMESPACE = "https://wiki.freecad.org/Package_Metadata"
NAMESPACE = {"pkg": PACKAGE_NAMESPACE}
REQUIRED_FILES = (
    "README.md",
    "README_ja.md",
    "Overview.md",
    "LICENSE",
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "Init.py",
    "InitGui.py",
    "package.xml",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
    ".github/workflows/ci.yml",
)
RAW_REPOSITORY_URL = "https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/"


def fail(message: str) -> None:
    raise AssertionError(message)


def required_text(root, tag: str) -> str:
    element = root.find(f"pkg:{tag}", NAMESPACE)
    if element is None or not (element.text or "").strip():
        fail(f"package.xml is missing <{tag}>")
    return element.text.strip()


def validate_manifest() -> None:
    package_path = REPOSITORY_ROOT / "package.xml"
    root = ElementTree.parse(package_path).getroot()
    if root.tag != f"{{{PACKAGE_NAMESPACE}}}package":
        fail("package.xml uses the wrong namespace")
    if root.attrib.get("format") != "1":
        fail("package.xml must use format 1")

    for tag in (
        "name",
        "description",
        "version",
        "date",
        "maintainer",
        "license",
        "icon",
        "content",
    ):
        if tag == "content":
            if root.find("pkg:content", NAMESPACE) is None:
                fail("package.xml is missing <content>")
        else:
            required_text(root, tag)

    version = required_text(root, "version")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        fail(f"package.xml version is not semantic: {version}")
    date = required_text(root, "date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        fail(f"package.xml date must use YYYY-MM-DD: {date}")
    if required_text(root, "freecadmin") != "1.0.0":
        fail("package.xml must declare FreeCAD 1.0.0 or later")
    if required_text(root, "pythonmin") != "3.11":
        fail("package.xml must declare Python 3.11 or later")

    maintainer = root.find("pkg:maintainer", NAMESPACE)
    if not maintainer.attrib.get("email"):
        fail("package.xml maintainer must include an email")

    repository_urls = [
        element
        for element in root.findall("pkg:url", NAMESPACE)
        if element.attrib.get("type") == "repository"
    ]
    if len(repository_urls) != 1:
        fail("package.xml must contain one repository URL")
    if repository_urls[0].attrib.get("branch") != "main":
        fail("package.xml repository URL must declare branch=main")
    if (repository_urls[0].text or "").strip() != (
        "https://github.com/ProProPrin/FreeCAD-AutoBodyExport"
    ):
        fail("package.xml repository URL is incorrect")

    readme_urls = [
        (element.text or "").strip()
        for element in root.findall("pkg:url", NAMESPACE)
        if element.attrib.get("type") == "readme"
    ]
    if readme_urls != [RAW_REPOSITORY_URL + "Overview.md"]:
        fail("package.xml readme URL must point to raw Overview.md")

    if root.find("pkg:content/pkg:other", NAMESPACE) is None:
        fail("package.xml must classify this extension as <other>")
    if root.find("pkg:content/pkg:workbench", NAMESPACE) is not None:
        fail("Auto Body Export is not a workbench")

    icon_path = REPOSITORY_ROOT / required_text(root, "icon")
    if not icon_path.is_file():
        fail(f"package icon does not exist: {icon_path}")
    ElementTree.parse(icon_path)


def validate_documentation() -> None:
    for relative_path in REQUIRED_FILES:
        if not (REPOSITORY_ROOT / relative_path).is_file():
            fail(f"required release file is missing: {relative_path}")

    overview_image_urls = re.findall(
        r"!\[[^\]]*\]\(([^)]+)\)",
        (REPOSITORY_ROOT / "Overview.md").read_text(encoding="utf-8"),
    )
    if len(overview_image_urls) < 2:
        fail("Overview.md must contain the selection and preferences images")
    documentation_files = ("Overview.md", "README.md", "README_ja.md")
    for documentation_file in documentation_files:
        content = (REPOSITORY_ROOT / documentation_file).read_text(encoding="utf-8")
        image_urls = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", content)
        for image_url in image_urls:
            if not image_url.startswith(RAW_REPOSITORY_URL):
                fail(f"{documentation_file} image must use the repository raw URL: {image_url}")
            relative_path = image_url.removeprefix(RAW_REPOSITORY_URL)
            if not (REPOSITORY_ROOT / relative_path).is_file():
                fail(f"documented image does not exist: {relative_path}")

    for markdown_path in REPOSITORY_ROOT.glob("*.md"):
        content = markdown_path.read_text(encoding="utf-8")
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", content):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative_path = target.split("#", 1)[0]
            if relative_path and not (markdown_path.parent / relative_path).exists():
                fail(f"broken local link in {markdown_path.name}: {target}")

    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for required_value in (
        "1.0.2",
        "1.1.1",
        "actions/checkout@v6",
        "actions/setup-python@v6",
        "ruff check",
        "ruff format --check",
    ):
        if required_value not in workflow:
            fail(f"CI workflow is missing required validation: {required_value}")


def validate_python_sources() -> None:
    source_roots = (
        REPOSITORY_ROOT / "freecad",
        REPOSITORY_ROOT / "tests",
        REPOSITORY_ROOT / "tools",
    )
    source_files = [REPOSITORY_ROOT / "Init.py", REPOSITORY_ROOT / "InitGui.py"]
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            if any(part.startswith("tmp") for part in path.parts):
                continue
            source_files.append(path)
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def main() -> int:
    try:
        validate_manifest()
        validate_documentation()
        validate_python_sources()
    except (AssertionError, ElementTree.ParseError, OSError) as error:
        print(f"Release validation failed: {error}", file=sys.stderr)
        return 1
    print("Release validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
