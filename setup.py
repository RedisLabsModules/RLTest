from setuptools import setup, find_packages


def read_version(version_file):
    """
    Given the input version_file, this function extracts the
    version info from the __version__ attribute.
    """
    version_str = None
    import re
    verstrline = open(version_file, "rt").read()
    VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(VSRE, verstrline, re.M)
    if mo:
        version_str = mo.group(1)
    else:
        raise RuntimeError("Unable to find version string in %s." % (version_file,))
    return version_str

setup(
    name='RLTest',
    version=read_version("RLTest/_version.py"),
    description="Redis Labs Test Framework, allow to run tests on redis and modules on a variety of environments.",
    author='RedisLabs',
    author_email='oss@redislabs.com',
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
