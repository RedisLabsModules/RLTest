from setuptools import setup, find_packages
setup(
    name='RLTest',
    version='0.2.1',
    packages=find_packages(),
    install_requires=[
        'redis>=3.0.0,<3.5.0',
        'redis-py-cluster>=1.3.4',
        'psutil'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
