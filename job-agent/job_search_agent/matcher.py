"""Job Matcher sub-agent.

Compares the structured resume (produced by the parser, read from session
state) against a job description the user pastes, and reports fit.

Design note — division of labor between tool and LLM:
  - score_skill_overlap (deterministic function tool): exact, reproducible
    evidence of which resume skills literally appear in the JD. Numbers
    the judges can verify.
  - the LLM: qualitative analysis on top — transferable skills, seniority
    fit, gap advice. Things keyword matching cannot do.
Giving the LLM deterministic evidence first anchors its analysis and
reduces hallucinated "matches".

Tool placement note: this is a plain ADK function tool, NOT an MCP tool.
Rule of thumb used in this project: capabilities reusable across systems
(file parsing) live in the MCP server; helper logic private to one agent
(this scorer) stays a local function. ADK freely mixes both in one agent.
"""

import re

from google.adk.agents import LlmAgent


def score_skill_overlap(resume_skills: list[str], job_description: str) -> dict:
    """Check which resume skills literally appear in a job description.

    Args:
        resume_skills: Flat list of skills from the structured resume.
        job_description: The full job posting text.

    Returns:
        dict with matched skills, unmatched skills, and coverage ratio.
    """
    jd = job_description.lower()
    matched, unmatched = [], []
    for skill in resume_skills:
        # Normalize "Python (primary)" -> "python" before searching, and
        # require word boundaries so "R" doesn't match inside "React".
        core = re.sub(r"\s*\(.*?\)", "", skill).strip().lower()
        if core and re.search(rf"(?<!\w){re.escape(core)}(?!\w)", jd):
            matched.append(skill)
        else:
            unmatched.append(skill)
    total = len(matched) + len(unmatched)
    return {
        "matched_skills": matched,
        "unmatched_skills": unmatched,
        "coverage": round(len(matched) / total, 2) if total else 0.0,
    }


INSTRUCTION = """\
You are a job-fit analyst. Respond in English or Traditional Chinese based on the user's language.

The candidate's structured resume (may be empty if not parsed yet):
{structured_resume?}

Procedure:
1. If the resume above is empty, tell the user to provide a resume file
   for parsing first, and stop.
2. Ask for a job description if the user hasn't pasted one.
3. Call score_skill_overlap with the resume's skills list and the job
   description to get deterministic overlap evidence.
4. Produce a fit report grounded in BOTH the tool result and the resume:
   - Match Summary (cite the coverage number from the tool)
   - Directly Matched Skills (from matched_skills)
   - Relevant but Not Directly Matched Experience (your analysis: transferable skills, projects)
   - Gaps and Recommendations (missing requirements; how to address them)
Base every claim on the resume or the JD. Do not invent experience.
"""

job_matcher = LlmAgent(
    name="job_matcher",
    model="gemini-2.5-flash",
    description=(
        "Use for comparing an ALREADY-PARSED resume against a job "
        "description. Input: a pasted job description. Output: fit report."
    ),
    instruction=INSTRUCTION,
    tools=[score_skill_overlap],  # plain function -> ADK wraps it automatically
    output_key="fit_report",
)
