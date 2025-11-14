
# This attribute is the only one place that the version number is written down,
# so there is only one place to change it when the version number changes.
try:
    from importlib.metadata import version
    __version__ = version('RLTest')
except Exception:
    __version__ = "99.99.99"  # like redis modules
