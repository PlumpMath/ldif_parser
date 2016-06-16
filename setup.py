#!/usr/bin/env python2

from setuptools import setup

setup(
    name='ldif_parser',
    version='0.1',
    description='Parse LDAP groups in the form of LDIF data and create a report on members',
    author='Peter Brown',
    license='MIT',
    packages=['ldif_parser'],
    install_requires=['mock',],
    include_package_data=True,
    zip_safe=False)

