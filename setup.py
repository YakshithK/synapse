# setup.py
from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agent-synapse",
    version="0.1.2",  # Updated version for agent-synapse
    author="Yakshith Kommineni",
    author_email="yakshith.kommineni@gmail.com",
    description="Kubernetes-like orchestration system for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YakshithK/synapse",
    packages=find_packages(
        exclude=["venv", "tests", "examples", "scripts", "dashboard"]
    ),
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
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "isort",
            "mypy",
            "pytest-cov",
            "pre-commit",
        ],
    },
    entry_points={
        "console_scripts": [
            "synapse=synapse.cli:app",
        ],
    },
    include_package_data=True,
    package_data={
        "synapse": [
            "py.typed",
            "templates/*.html",  # Include dashboard templates
            "static/*",  # Include static files
        ],
    },
    project_urls={
        "Documentation": "https://github.com/YakshithK/synapse#readme",
        "Bug Reports": "https://github.com/YakshithK/synapse/issues",
        "Source": "https://github.com/YakshithK/synapse",
    },
)
