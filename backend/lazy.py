"""Lazy stand-ins for heavy libraries, so they load on first use, not at startup.

openai costs ~19 MB and scikit-learn ~79 MB of process memory. Importing them
at module level makes every web process and every beat_tick run pay for them
even when no AI feature is used.
"""


def OpenAI(*args, **kwargs):
    """Drop-in for `openai.OpenAI(...)`; imports the SDK on first call."""
    from openai import OpenAI as _OpenAI

    return _OpenAI(*args, **kwargs)


class LazyOpenAIClient:
    """Drop-in for a module-level `client = OpenAI()`; built on first attribute access."""

    def __init__(self, *args, **kwargs):
        self._args, self._kwargs, self._client = args, kwargs, None

    def __getattr__(self, name):
        if self._client is None:
            self._client = OpenAI(*self._args, **self._kwargs)
        return getattr(self._client, name)
