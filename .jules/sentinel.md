## 2024-05-18 - Information Exposure in Agent Error Messages
**Vulnerability:** The application was leaking its internal absolute file system paths (e.g., `C:\path\to\allowed\directory`) in the `job-agent/job_search_agent/security.py` callback when an invalid file path was requested by the user.
**Learning:** Error messages returned to the LLM agent are ultimately proxied back to the user. Detailed paths can expose the underlying file system structure, enabling reconnaissance for subsequent attacks.
**Prevention:** Avoid embedding absolute internal paths or sensitive contextual data in error messages intended for external consumption. Ensure robust handling of edge-case inputs (such as missing strings causing `None` values) by enforcing default typing prior to path-resolution logic.
