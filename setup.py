from setuptools import setup, find_packages
setup(
    name='RLTest',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'redis>=2.10.5,<3.1.0',
        'redis-py-cluster',
        'psutil'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
