from setuptools import setup, find_packages
setup(
    name='RLTest',
    version='0.2.1',
    packages=find_packages(),
    install_requires=[
        'redis>=3.0.0,<3.5.0',
        'redis-py-cluster @ git+ssh://git@github.com/Grokzen/redis-py-cluster.git@master#egg=redis-py-cluster',
        'psutil'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
