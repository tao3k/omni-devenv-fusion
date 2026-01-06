# Agent package for omni-dev-fusion

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("omni-dev-fusion-agent")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
