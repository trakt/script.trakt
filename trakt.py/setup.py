from trakt import __version__

from setuptools import setup

setup(
    name='trakt.py',
    version=__version__,
    license='MIT',
    url='https://github.com/fuzeman/trakt.py',

    author='Dean Gardiner',
    author_email='me@dgardiner.net',

    description='Python interface for the trakt.tv API',
    packages=['trakt'],
    platforms='any',

    install_requires=[
        'requests'
    ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python'
    ],
)
