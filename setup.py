from setuptools import setup, find_packages
setup(
    name='RLTest',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'networkx',
        'matplotlib',
        'redis>=2.10.5'
    ],
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
