"""ADK convention: `adk web` scans the current directory for packages
whose __init__.py imports an `agent` module exposing `root_agent`.
This file is the discovery hook — without it the agent won't appear
in the adk web dropdown."""

from . import agent
