from setuptools import setup, find_packages

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.txt'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='PyISY',
    version='1.1.2',
    license='Apache License 2.0',
    url='http://automic.us/projects/pyisy',
    author='Ryan Kraus',
    author_email='automicus@gmail.com',
    description='Python module to talk to ISY994 from UDI.',
    long_description=long_description,
    long_description_content_type='text/plain',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=['requests', 'VarEvents'],
    keywords=['home automation', 'isy', 'isy994', 'isy-994', 'UDI'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
