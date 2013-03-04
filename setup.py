import os

from setuptools import setup, find_packages

if os.path.exists('README.rst'):
    with open('README.rst') as file:
        long_description = file.read()
else:
    long_description = ''

setup(
    name="spinoff",
    description="Framework for writing distributed, fault tolerant and scalable internet applications",
    long_description=long_description,
    version="0.7.2",
    packages=find_packages() + ['geventreactor'],

    install_requires=[
        'zope.interface',
        'twisted>=12.0',
        'pyzmq==13.0',
        'gevent==1.0dev',
        'lockfile==0.9.1',
    ],

    author="Erik Allik",
    author_email="erik.allik@skype.net",
    license="BSD",
    url="http://github.com/eallik/spinoff/"
)
