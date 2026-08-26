"""Hole as an MCP server -- the same local pipeline, a third interface.

CLI and the web UI already share one backend (jobsearch/*.py); this package
adds a conversational front door onto that same backend rather than
building a fourth thing. Every tool here calls a function that already
exists and is already exercised by the other two interfaces -- there is no
tailoring, scoring, or dispatch logic that lives only in this package.

Runs over stdio, launched as a local subprocess by the MCP client (Claude
Code, Claude Desktop). Nothing here talks to a hosted backend and nothing
here uploads your data anywhere -- the whole point of building this instead
of pointing at a third-party MCP job-search service.
"""
