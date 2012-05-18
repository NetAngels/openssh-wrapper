#!/usr/bin/env python
import os
from distutils.core import setup

def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except:
        return ''

setup(
    name='openssh-wrapper',
    version='0.3.2',
    description='OpenSSH python wrapper',
    author='NetAngels team',
    author_email='info@netangels.ru',
    url='https://github.com/NetAngels/openssh-wrapper',
    long_description = read('README.rst'),
    license = 'BSD License',
    py_modules=['openssh_wrapper'],
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ),
)
