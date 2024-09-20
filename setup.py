#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="pyiskra",
    version="0.1.12",
    description="Python Iskra devices interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Iskra d.o.o.",
    author_email="razvoj.mis@iskra.eu",
    maintainer=", ".join(("Iskra <razvoj.mis@iskra.eu>",)),
    license="GPL",
    url="https://github.com/Iskramis/pyiskra",
    python_requires=">=3.8",
    packages=find_packages(),
    keywords=["homeautomation", "iskra", "energy meter"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Home Automation",
    ],
    install_requires=["aiohttp", "pymodbus", "psutil", "ipaddress"],
)
