from setuptools import find_packages, setup

setup(
    name="spotify-memory-contracts",
    version="0.1.0",
    description="Shared Pydantic data contracts for Spotify Personalized AI Memory System",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0"
    ],
    python_requires=">=3.9",
)
