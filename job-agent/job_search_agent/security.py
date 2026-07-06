"""Security guardrails for the job-search agent system.

Capstone security rubric item — defense in depth, two layers:
  Layer 1 (MCP server, Day 1): extension allowlist + file-size cap.
  Layer 2 (agent, this file):  directory allowlist enforced BEFORE any
                               tool call leaves the agent.

Why both? The server can't know which directories the *user* considers
private; the agent can't guarantee every future tool validates its own
inputs. Each layer covers the other's blind spot.
"""

import os
from pathlib import Path
from typing import Any, Optional

# Default allowlist root = the project folder (kaggle/), two levels above
# this package. Overridable per-deployment without code changes:
#   set RESUME_ALLOWED_DIR=C:\some\other\folder
DEFAULT_ALLOWED_DIR = Path(__file__).resolve().parents[2]


def enforce_path_allowlist(
    tool: Any, args: dict, tool_context: Any
) -> Optional[dict]:
    """before_tool_callback: block file access outside the allowed directory.

    ADK callback contract:
      return None  -> allow the tool call to proceed unchanged;
      return dict  -> SHORT-CIRCUIT: this dict becomes the tool's result
                      and the real tool is never executed.

    This stops path-traversal attempts (e.g. a prompt-injected resume
    telling the agent to read C:/Users/x/.ssh/id_rsa) at the agent
    boundary, before the request ever reaches the MCP server.
    """
    if tool.name != "extract_resume_text":
        return None  # guardrail only applies to file-reading tools

    base = Path(os.getenv("RESUME_ALLOWED_DIR", DEFAULT_ALLOWED_DIR)).resolve()
    raw_path = args.get("file_path", "")
    try:
        # Prevent TypeError if args.get() returns None instead of a string
        if raw_path is None:
            raw_path = ""
        target = Path(raw_path).expanduser().resolve()
    except TypeError:
        return {"result": "BLOCKED_BY_POLICY: Invalid file path provided."}

    if not target.is_relative_to(base):
        # Prevent information exposure: Do not leak the absolute path of `base`
        # Tell the model WHY it was blocked without exposing the server path
        return {
            "result": (
                f"BLOCKED_BY_POLICY: The requested file is outside the allowed "
                f"resume directory. Ask the user to provide a valid path or move "
                "the file into the allowed directory."
            )
        }
    return None
