"""Setup configuration for A2A Summit Demo package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="a2a-summit-demo",
    version="1.0.0",
    author="A2A Summit Demo Team",
    description="Multi-Agent Tourist Scheduling System with Real-time UI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/muscariello/a2a-summit-demo",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "a2a-scheduler=agents.scheduler_agent:main",
            "a2a-guide=agents.guide_agent:main",
            "a2a-tourist=agents.tourist_agent:main",
            "a2a-ui=agents.ui_agent:main",
            "a2a-autonomous-guide=agents.autonomous_guide_agent:main",
            "a2a-autonomous-tourist=agents.autonomous_tourist_agent:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)