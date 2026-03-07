#!/usr/bin/env python3
"""Setup configuration for DJI OSD Tool."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dji-osd-tool",
    version="2.2.0",
    author="Devsur11",
    description="DJI Avata OSD Overlay Tool - Create professional OSD overlays for drone footage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Devsur11/dji-osd-tool",
    py_modules=["dji_osd_tool"],
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.8.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
    ],
    entry_points={
        "console_scripts": [
            "dji-osd-tool=dji_osd_tool:cli_main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video",
    ],
)
