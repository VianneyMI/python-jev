"""Unofficial typed Python SDK for TypeSafe's Jev.

Jev is TypeSafe's System One model: it reads a state (text or JSON) and answers typed questions
about it with probabilities, all questions in one call. This package represents TypeSafe's
primitives (noul, choice, score) as Pydantic classes whose instances are typed answers.

This package is not affiliated with or endorsed by TypeSafe. See https://docs.typesafe.ai for
TypeSafe's documentation.
"""

from jev._version import __version__

__all__ = ["__version__"]
