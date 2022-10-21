[tool.poetry]
name = "RLTest"
version = "0.5.9"
description="Redis Labs Test Framework, allow to run tests on redis and modules on a variety of environments"
authors = ["RedisLabs <oss@redislabs.com>"]
license = "BSD-3-Clause"
readme = "README.md"

packages = [
    { include = 'RLTest' },
]

classifiers = [
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
]

[tool.poetry.dependencies]
python = ">= 3.6.0"
distro = "^1.5.0"
redis = "^4.2.2"
psutil = "5.8.0" # 5.9.0 currently broken on macOS
pytest-cov = "2.5"

[tool.poetry.urls]
repository = "https://github.com/RedisLabsModules/RLTest"

[tool.poetry.scripts]
RLTest = 'RLTest.__main__:main'

[tool.poetry.dev-dependencies]
codecov = "*"
flake8 = "*"
rmtest = "^0.7.0"
nose = "^1.3.7"
ml2rt = "^0.2.0"
pytest = "^6.0"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
