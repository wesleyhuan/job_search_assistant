"""Resume Parser Agent (Day 2: single agent + MCP toolset).

Architecture note: this agent owns the *intelligence* of the pipeline —
turning raw resume text into schema-conformant JSON — while all
deterministic work (file I/O, validation) lives in the MCP server. The
agent never touches files directly; it only acts through MCP tools.

Run from the parent folder (job-agent/):  adk web
Requires .env in this package folder with GOOGLE_API_KEY (see .env.example).
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

# Locate the MCP server relative to THIS file, so the project works no
# matter which directory `adk web` is launched from. Layout assumed:
#   kaggle/
#   ├── resume-mcp-server/server.py
#   └── job-agent/resume_agent/agent.py   <- we are here
SERVER_PATH = Path(__file__).resolve().parents[2] / "resume-mcp-server" / "server.py"

resume_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            # sys.executable = the exact Python running this agent. Using it
            # instead of the bare string "python" avoids two classic Windows
            # failures: "python" not on PATH, or resolving to a different
            # interpreter/venv that doesn't have fastmcp installed.
            command=sys.executable,
            args=[str(SERVER_PATH)],
        ),
        # First tool call spawns the server subprocess; give it headroom.
        timeout=30,
    ),
)

# The instruction encodes the agentic loop as an explicit procedure.
# Note the self-correction step (5): validate_resume returns field-level
# errors precisely so the model can repair its own output — this is the
# behavior to demo in the capstone video.
INSTRUCTION = """\
You are a resume parsing specialist. Your job: convert a resume file into
validated, structured JSON.

Follow this procedure strictly:
1. Ask the user for the resume file path if they haven't provided one.
2. Call get_resume_schema to learn the exact target JSON format.
3. Call extract_resume_text with the file path to get the raw text.
   If it returns EXTRACTION_FAILED, explain the reason to the user and stop.
4. Structure the raw text into a JSON object that conforms to the schema.
   Rules:
   - Copy facts verbatim; NEVER invent information not present in the text.
   - Omit optional fields you cannot find rather than guessing.
   - Preserve the original language of the resume (do not translate).
   - Pass the raw JSON string ONLY: no markdown fences, no commentary.
   - Fill EVERY section present in the resume, including projects and certifications.
5. Call validate_resume with your JSON string.
   - If it returns INVALID, read the field errors, fix your JSON, and
     validate again (at most 3 attempts).
   - If it returns VALID, present the normalized JSON to the user inside
     a ```json code block, plus a 2-3 sentence summary of the candidate.

Privacy: the resume contains personal data. Only display it to the user
who provided the file; never store it or repeat it in later unrelated
turns.
"""

root_agent = LlmAgent(
    name="resume_parser_agent",
    model="gemini-2.5-flash",  # fast + cheap; enough for extraction tasks
    description="Parses resume files (PDF/DOCX/TXT) into validated structured JSON.",
    instruction=INSTRUCTION,
    tools=[resume_toolset],
)
