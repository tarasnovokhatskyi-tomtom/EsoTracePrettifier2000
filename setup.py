from setuptools import setup, find_packages


with open("requirements.txt") as f:
    requirements = f.read().split()

setup(
    version="0.1",
    name="eso_trace_prettifier",
    packages=["eso_trace_prettifier"],
    install_requires=requirements,
    entry_points={"console_scripts": ["prettify-logs=eso_trace_prettifier.main:cli"]},
)
