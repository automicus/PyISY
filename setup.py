from setuptools import setup, find_packages

setup(
    name='PyISY',
    version='1.1.0',
    license='Apache License 2.0',
    url='http://automic.us/projects/pyisy',
    download_url='https://github.com/automicus/pyisy/tarball/1.1.0',
    author='Ryan Kraus',
    author_email='automicus@gmail.com',
    description='Python module to talk to ISY994 from UDI.',
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
