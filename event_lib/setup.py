from setuptools import setup, find_packages

setup(
    name="event_lib",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "polars>=0.8.0"
    ],
    python_requires='>=3.8',
)