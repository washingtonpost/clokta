''' Define executable setup '''
from setuptools import setup

setup(
    name='clokta',
    version='0.1',
    py_modules=['clokta'],
    install_requires=[
        'Click',
        'boto3',
        'requests',
        'bs4',
        'pyyaml'
    ],
    entry_points={
        'console_scripts': [
            'clokta=cli.role:assume_role'
        ]
    }
)
