"""
Setup script for Linguard CLI.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path, "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read long description
readme_path = Path(__file__).parent.parent.parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, "r") as f:
        long_description = f.read()

setup(
    name="linguard-cli",
    version="0.1.0",
    description="Command line interface for Linguard VPN Manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Linguard Team",
    author_email="linguard@example.com",
    url="https://github.com/joseantmazonsb/linguard",
    package_dir={"": ".."},
    packages=["linguard_cli"],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "linguard=linguard_cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
        "Topic :: System :: Networking",
    ],
)
