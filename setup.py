''' Define executable setup '''
import os
from setuptools import setup, find_packages
import warnings

setup(
    name='clokta',
    version='0.8',
    packages=find_packages(),
    include_package_data=True,
    py_modules=['clokta'],
    install_requires=[
        'Click',
        'boto3',
        'requests',
        'bs4',
        'configparser',
        'enum-compat',
        'pyyaml',
        'six',
        'pyaml'
    ],
    entry_points={
        'console_scripts': [
            'clokta=cli.role:assume_role'
        ]
    },
    namespace_packages = ['cli'],
    author="Robert Antonucci and the WaPo platform tools team",
    author_email="opensource@washingtonpost.com",
    url="https://github.com/washingtonpost/clokta",
    download_url="https://github.com/washingtonpost/clokta/tarball/v0.8",
    keywords=['okta', 'clokta', 'aws', 'cli'],
    classifiers=[]
)
