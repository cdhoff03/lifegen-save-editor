"""Single source of truth for the app version.

This file is overwritten by CI (see .github/workflows/release.yml) when
building from a tag. In the source tree it stays at the dev sentinel below.
"""
__version__ = "0.0.0-dev"
