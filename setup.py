from setuptools import setup


with open("requirements.txt") as f:
    requirements = f.read().split()

setup(
    version="0.1",
    name="OptimusPrime",
    scripts=["main.py"],
    install_requires=requirements,
    entry_points={"console_scripts": ["prettify-logs=main:prettify_logs"]},
)
