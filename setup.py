#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="RLTest",
    description="Redis Labs Test Framework, allow to run tests on redis and modules on a variety of environments",
    long_description=open("README.md").read().strip(),
    long_description_content_type="text/markdown",
    keywords=["Redis", "key-value store", "database"],
    license="BSD-3-Clause",
    version="0.5.9",
    packages=find_packages(
        include=[
            "RLTest",
            "RLTest.Enterprise",
        ]
    ),
    url="https://github.com/RedisLabsModules/RLTest",
    project_urls={
        "Documentation": "https://github.com/RedisLabsModules/RLTest",
        "Changes": "https://github.com/RedisLabsModules/RLTest/releases",
        "Code": "https://github.com/RedisLabsModules/RLTest",
        "Issue tracker": "https://github.com/RedisLabsModules/RLTest/issues",
    },
    author="Redis Inc.",
    author_email="oss@redis.com",
    python_requires=">=3.6",
    install_requires=[
        "distro ~= 1.5.0",
        "redis ~= 4.3.4",
        "psutil ~= 5.8.0",
    ],
    classifiers=[
        'Topic :: Database',
        'Programming Language :: Python',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: BSD License',
        'Development Status :: 5 - Production/Stable'
    ],
    extras_require={
    },
)
