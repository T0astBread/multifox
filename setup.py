# pylint: disable=missing-module-docstring

from setuptools import find_packages, setup

setup(
    name="multifox",
    version="0.0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["click", "pygobject", "pyyaml"],
    entry_points={
        "console_scripts": [
            "multifox = multifox.cli:cli",
        ],
    },
)
