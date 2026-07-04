"""Resume Parser sub-agent.

Owns one job: file -> validated structured JSON. All file I/O and
validation happen through the MCP server; the LLM only does the
text -> JSON structuring step.
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

from .security import enforce_path_allowlist

SERVER_PATH = Path(__file__).resolve().parents[2] / "resume-mcp-server" / "server.py"

resume_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,  # same interpreter/venv as the agent
            args=[str(SERVER_PATH)],
        ),
        timeout=30,
    ),
)

# Lessons from Day 2 debugging are baked into these rules:
# - "raw JSON only, no fences" -> the Extra-data validation failure
# - "fill EVERY section"       -> projects/certifications were silently dropped
# - "Traditional Chinese"      -> model drifted to Simplified Chinese
INSTRUCTION = """\
You are a resume parsing specialist. Convert a resume file into validated,
structured JSON. Respond in English or Traditional Chinese based on the user's language.

Procedure:
1. If no file path was provided, ask the user for one.
2. Call get_resume_schema to learn the exact target JSON format.
3. Call extract_resume_text with the file path.
   If it returns EXTRACTION_FAILED or BLOCKED_BY_POLICY, explain why to
   the user and stop.
4. Structure the raw text into JSON conforming to the schema. Rules:
   - Copy facts verbatim; NEVER invent information not in the text.
   - Fill EVERY section present in the resume, including projects and
     certifications — do not skip optional fields that have source data.
   - Omit optional fields with no source data rather than guessing.
   - Preserve the resume's original language; do not translate.
5. Call validate_resume with the raw JSON string ONLY — no markdown
   fences, no commentary before or after the JSON.
   - INVALID -> read the field errors, fix, re-validate (max 3 attempts).
   - VALID   -> reply with the normalized JSON in a ```json block, then a
     2-3 sentence candidate summary in Traditional Chinese.

Privacy: resume content is personal data; only show it to the user who
provided the file.
"""

resume_parser = LlmAgent(
    name="resume_parser",
    model="gemini-2.5-flash",
    # The orchestrator's LLM routes requests by reading this description —
    # write it like a routing rule, not marketing copy.
    description=(
        "Use for parsing a resume FILE (PDF/DOCX/TXT path) into structured "
        "JSON. Input: a file path. Output: validated resume JSON."
    ),
    instruction=INSTRUCTION,
    tools=[resume_toolset],
    before_tool_callback=enforce_path_allowlist,
    # output_key: the agent's final response is saved to session state
    # under this key, where other agents can read it via {structured_resume?}
    # instruction templating. This is how the parser hands its result to
    # the matcher without them ever talking directly.
    output_key="structured_resume",
)
