''' Define executable setup '''
import os
from setuptools import setup, find_packages
import warnings

setup(
    name='clokta',
    version='4.1.0',
    packages=find_packages(),
    include_package_data=True,
    py_modules=['clokta'],
    install_requires=[
        'beautifulsoup4',
        'boto3',
        'click',
        'configparser',
        'enum-compat',
        'keyring',
        'requests'
    ],
    entry_points={
        'console_scripts': [
            'clokta=clokta.cloktacli:assume_role'
        ]
    },
    namespace_packages=['clokta'],
    author="Robert Antonucci and the WaPo platform tools team",
    author_email="opensource@washingtonpost.com",
    url="https://github.com/washingtonpost/clokta",
    download_url="https://github.com/washingtonpost/clokta/tarball/4.1.0",
    keywords=['okta', 'clokta', 'aws', 'cli'],
    classifiers=[]
)
