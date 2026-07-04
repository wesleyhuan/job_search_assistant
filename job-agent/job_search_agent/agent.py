"""Job Search Assistant — root orchestrator.

Multi-agent architecture (ADK LLM-driven delegation):

    job_search_orchestrator          (routing + conversation)
    ├── resume_parser   -> MCP server tools (extract / schema / validate)
    │                      + path-allowlist security callback
    │                      + output_key="structured_resume"
    └── job_matcher     -> local function tool (score_skill_overlap)
                           + reads {structured_resume?} from session state

How delegation works: listing sub_agents lets ADK offer the root LLM a
transfer action; the LLM picks a sub-agent by reading its `description`.
The state key `structured_resume` is the data bus between the two
sub-agents — they never call each other directly.
"""

from google.adk.agents import LlmAgent
from .matcher import job_matcher
from .parser import resume_parser
from .writer import job_cover_letter_writer

INSTRUCTION = """\
You are Job Search Assistant, the coordinator of a resume-parsing
and job-matching system. Respond in English or Traditional Chinese based on the user's language.

Routing rules:
- User provides a resume file path, or asks to parse/re-parse a resume
  -> transfer to resume_parser.
- User pastes a job description or asks about job fit
  -> transfer to job_matcher.
- User asks for a cover letter 
  -> transfer to job_cover_letter_writer.
- Anything else: answer briefly yourself and explain what you can do
  (1. Parse resume file 2. Compare job fit 3. Write cover letter), then ask what they'd like.

Do not attempt to parse resumes or analyze job fit yourself — always
delegate to the specialist.
"""

root_agent = LlmAgent(
    name="job_search_orchestrator",
    model="gemini-2.5-flash",
    description="Coordinator that routes between resume parsing and job matching.",
    instruction=INSTRUCTION,
    sub_agents=[resume_parser, job_matcher, job_cover_letter_writer],
)
