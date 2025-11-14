# setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="synapse",
    version="0.1.0",
    author="Yakshith Kommineni",
    author_email="yakshith.kommineni@gmail.com",
    description="Kubernetes-like orchestration system for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YakshithK/synapse",
    packages=find_packages(exclude=["venv", "tests", "examples", "scripts", "dashboard"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "typer>=0.9.0",
        "pyyaml>=6.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "jinja2>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "synapse=synapse.cli:app",
        ],
    },
    include_package_data=True,
    package_data={
        "synapse": ["py.typed"],
    },
)