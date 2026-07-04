"""In-memory tests for the Resume Parser MCP server.

FastMCP lets a Client connect directly to the server object in the same
process — no subprocess, no network. This makes MCP servers as easy to
test as plain functions. Run with:  python test_server.py
"""

import asyncio
import json
from pathlib import Path

from docx import Document
from fastmcp import Client

from server import mcp

SAMPLES = Path(__file__).parent / "samples"


def make_sample_files() -> None:
    """Create small sample resumes (txt + docx) used by the tests."""
    SAMPLES.mkdir(exist_ok=True)

    resume_text = (
        "Wei-Lun Chen\n"
        "Taipei, Taiwan | weilun.chen@example.com | github.com/weilunc\n\n"
        "SUMMARY\n"
        "Python developer focused on AI agents and developer tooling.\n\n"
        "EXPERIENCE\n"
        "Acme AI — Junior Developer (2024-03 to present)\n"
        "- Built resume parsing pipeline with pypdf and Pydantic\n"
        "- Automated job-search workflows with MCP servers\n\n"
        "EDUCATION\n"
        "National Taiwan University — B.S. Computer Science (2020 to 2024)\n\n"
        "SKILLS\n"
        "Python, FastMCP, Pydantic, Git\n"
    )
    (SAMPLES / "resume.txt").write_text(resume_text, encoding="utf-8")

    doc = Document()
    for line in resume_text.splitlines():
        doc.add_paragraph(line)
    doc.save(SAMPLES / "resume.docx")


VALID_RESUME_JSON = json.dumps(
    {
        "contact": {
            "name": "Wei-Lun Chen",
            "email": "weilun.chen@example.com",
            "location": "Taipei, Taiwan",
            "links": ["github.com/weilunc"],
        },
        "summary": "Python developer focused on AI agents and developer tooling.",
        "education": [
            {
                "institution": "National Taiwan University",
                "degree": "B.S. Computer Science",
                "start_date": "2020",
                "end_date": "2024",
            }
        ],
        "experience": [
            {
                "company": "Acme AI",
                "title": "Junior Developer",
                "start_date": "2024-03",
                "end_date": "present",
                "highlights": [
                    "Built resume parsing pipeline with pypdf and Pydantic",
                    "",  # empty highlight — should be stripped by the validator
                ],
            }
        ],
        "skills": ["Python", "FastMCP", "Pydantic", "Git"],
    }
)

INVALID_RESUME_JSON = json.dumps(
    {"contact": {"name": "", "email": "not-an-email"}}  # two schema violations
)


async def main() -> None:
    make_sample_files()

    async with Client(mcp) as client:
        # --- 1. tool discovery -------------------------------------------
        tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        print(f"[1] tools exposed: {names}")
        assert names == ["extract_resume_text", "get_resume_schema", "validate_resume"]

        # --- 2. text extraction (txt + docx) -----------------------------
        for fname in ["resume.txt", "resume.docx"]:
            result = await client.call_tool(
                "extract_resume_text", {"file_path": str(SAMPLES / fname)}
            )
            text = result.content[0].text
            assert "Wei-Lun Chen" in text and "FastMCP" in text
            print(f"[2] extracted {fname}: {len(text)} chars ✓")

        # --- 3. extraction failure path ----------------------------------
        result = await client.call_tool(
            "extract_resume_text", {"file_path": "does_not_exist.pdf"}
        )
        assert result.content[0].text.startswith("EXTRACTION_FAILED")
        print("[3] missing file handled gracefully ✓")

        result = await client.call_tool(
            "extract_resume_text", {"file_path": __file__.replace(".py", ".py")}
        )
        assert "Unsupported file type" in result.content[0].text
        print("[3] extension allowlist enforced ✓")

        # --- 4. validation: happy path ------------------------------------
        result = await client.call_tool(
            "validate_resume", {"resume_json": VALID_RESUME_JSON}
        )
        text = result.content[0].text
        assert text.startswith("VALID")
        assert '""' not in text  # empty highlight was stripped
        print("[4] valid resume accepted, normalized ✓")

        # --- 5. validation: error path ------------------------------------
        result = await client.call_tool(
            "validate_resume", {"resume_json": INVALID_RESUME_JSON}
        )
        text = result.content[0].text
        assert text.startswith("INVALID")
        assert "contact.name" in text and "contact.email" in text
        print(f"[5] invalid resume rejected with field errors ✓\n    -> {text[:120]}...")

        # --- 6. schema resource -------------------------------------------
        res = await client.read_resource("resume://schema")
        schema = json.loads(res[0].text)
        assert schema["title"] == "Resume"
        print(f"[6] schema resource readable, {len(schema['properties'])} top-level fields ✓")

    print("\nAll tests passed 🎉")


if __name__ == "__main__":
    asyncio.run(main())
