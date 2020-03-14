from setuptools import setup, find_packages

setup(
    name='RLTest',
    version='0.2.1',
    description="Redis Labs Test Framework, allow to run tests on redis and modules on verity of environments.",
    packages=find_packages(),
    install_requires=[
        'redis>=3.0.0',
        'redis-py-cluster@git+ssh://git@github.com/Grokzen/redis-py-cluster.git@master#egg=redis-py-cluster',
        'psutil'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
