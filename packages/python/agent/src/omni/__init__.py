__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from importlib.metadata import version as _version

try:
    __version__ = _version("omni-agent")
except Exception:
    __version__ = "0.4.0-dev"
