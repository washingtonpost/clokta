''' Define executable setup '''
from setuptools import setup

setup(
    name='clokta',
    version='0.2',
    packages=find_packages(),
    include_package_data=True,
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
    },
    author="Robert Antonucci and the WaPo platform tools team",
    author_email="opensource@washingtonpost.com",
    url="https://github.com/washingtonpost/clokta",
    download_url = "https://github.com/washingtonpost/clokta/tarball/v0.2",
    keywords = ['okta', 'clokta', 'aws', 'cli'],
    classifiers = []

)
