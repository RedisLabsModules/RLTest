from setuptools import setup, find_packages

setup(
    name='RLTest',
    version='0.2.1',
    description="Redis Labs Test Framework, allow to run tests on redis and modules on a variety of environments.",
    packages=find_packages(),
    install_requires=[
        'redis>=3.0.0',
        'redis-py-cluster>=2.1.0',
        'psutil',
        'distro>=1.4.0'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
