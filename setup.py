from setuptools import setup, find_packages
import io

def read_all(f):
    with io.open(f, encoding="utf-8") as file:
        return file.read()

requirements = list(map(str.strip, open("requirements.txt").readlines()))

setup(
    name='RLTest',
    version='0.2.1',
    description="Redis Labs Test Framework, allow to run tests on redis and modules on verity of environments.",
    long_description=read_all("README.md"),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    install_requires=requirements,
    entry_points='''
        [console_scripts]
        RLTest=RLTest.__main__:main
    '''
)
