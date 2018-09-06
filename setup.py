from setuptools import setup, find_packages
setup(
    name='RLTest',
    version='0.1',
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
