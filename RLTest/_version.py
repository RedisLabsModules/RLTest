
# This attribute is the only one place that the version number is written down,
# so there is only one place to change it when the version number changes.
try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution('RLTest').version
except (pkg_resources.DistributionNotFound, AttributeError, ImportError):
    __version__ = "99.99.99"  # like redis modules
