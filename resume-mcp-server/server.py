"""Resume Parser MCP Server (FastMCP).

Architecture note (capstone design decision):
This server deliberately contains NO LLM calls. It exposes deterministic
capabilities only:

    1. extract_resume_text  — file -> raw text
    2. validate_resume      — candidate JSON -> validated JSON or errors
    3. resource resume://schema — the JSON Schema the agent must target

The intelligent step (raw text -> structured JSON) is performed by the
ADK agent that consumes this server. Benefits of this split:
- The server needs no API keys (smaller attack surface, simpler config).
- Tools are deterministic, hence unit-testable and cacheable.
- The agent's LLM does the reasoning, which is the point of an agent.

Run locally for inspection:   fastmcp dev server.py
Run as stdio server (for ADK): python server.py
"""

import json

from fastmcp import FastMCP
from pydantic import ValidationError

from extractors import ExtractionError, extract_text
from schemas import Resume

mcp = FastMCP(
    name="resume-parser",
    instructions=(
        "Tools for parsing resumes. Typical flow: call extract_resume_text "
        "to get raw text, structure it into JSON matching the resume://schema "
        "resource, then call validate_resume to verify your JSON."
    ),
)


@mcp.tool
def extract_resume_text(file_path: str) -> str:
    """Extract raw text from a resume file (.pdf, .docx, or .txt).

    Args:
        file_path: Absolute or relative path to the resume file.

    Returns:
        The plain-text content of the resume.
    """
    try:
        return extract_text(file_path)
    except ExtractionError as e:
        # Return the failure as a message rather than raising, so the agent
        # receives a clean explanation it can act on (e.g. ask the user for
        # a different file) instead of an opaque tool error.
        return f"EXTRACTION_FAILED: {e}"


def _clean_llm_json(raw: str) -> tuple[str, str]:
    """Best-effort cleanup of LLM-produced JSON strings.

    LLMs habitually wrap JSON in markdown fences or append commentary.
    Tools called by LLMs should tolerate this (Postel's law: be liberal
    in what you accept) instead of failing on cosmetic noise.
    Returns (cleaned_json, note_about_what_was_stripped).
    """
    s = raw.strip()
    note = ""
    if s.startswith("```"):                      # strip ```json ... ``` fences
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        note = "stripped markdown fences; "
        s = s.strip()
    return s, note

@mcp.tool
def validate_resume(resume_json: str) -> str:
    """(docstring 不變)"""
    cleaned, note = _clean_llm_json(resume_json)

    # raw_decode parses the FIRST complete JSON value and tells us where it
    # ended — so trailing junk no longer kills the whole validation.
    try:
        data, end = json.JSONDecoder().raw_decode(cleaned)
    except json.JSONDecodeError as e:
        return f"INVALID: not valid JSON — {e}"

    trailing = cleaned[end:].strip()
    if trailing:
        note += f"ignored {len(trailing)} trailing chars after the JSON; "

    try:
        resume = Resume.model_validate(data)
    except ValidationError as e:
        # Compact, field-addressed errors: "contact.email: value is not a
        # valid email address". This format is easy for an LLM to map back
        # onto its own output and self-correct.
        issues = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        return f"INVALID: {issues}"

    return "VALID\n" + resume.model_dump_json(indent=2)


@mcp.tool
def get_resume_schema() -> str:
    """Get the JSON Schema that structured resumes must conform to.

    Call this BEFORE structuring a resume, so you know the exact field
    names and types to produce.

    Compatibility note: this duplicates the resume://schema resource on
    purpose. ADK's MCPToolset only consumes MCP *tools*, not resources,
    so agents built with ADK need a tool-shaped way to read the schema.
    """
    return json.dumps(Resume.model_json_schema(), indent=2)


@mcp.resource("resume://schema")
def resume_schema() -> str:
    """The JSON Schema for a structured resume.

    Exposed as a resource (not a tool) because it is static reference
    data: the agent reads it once to learn the target format, rather than
    'doing' anything with it.
    """
    return json.dumps(Resume.model_json_schema(), indent=2)


if __name__ == "__main__":
    # stdio transport: the standard way for a local client (ADK agent,
    # Claude Desktop, MCP Inspector) to spawn and talk to this server.
    mcp.run()
