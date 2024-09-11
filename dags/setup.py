from setuptools import find_packages, setup

setup(
    name="dags",
    version="0.0.1",
    packages=find_packages(),
    package_data={
        "dags": [
            "dbt-project/**/*",
        ],
    },
    install_requires=[
        "dagster",
        "dagster-cloud",
        "dagster-dbt",
        "dbt-postgres<1.9",
        "dbt-postgres<1.9",
    ],
    extras_require={
        "dev": [
            "dagster-webserver",
        ]
    },
)