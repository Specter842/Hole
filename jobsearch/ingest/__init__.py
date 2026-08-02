"""Ways to get real career history into the profile graph.

Three routes, in descending order of trust:

- `linkedin`  - deterministic CSV parsing of the archive LinkedIn gives you when
                you request your own data. No model involved, so rows land
                verified.
- `documents` - a resume, a performance review, a project write-up, notes. A
                model extracts structured entities; rows land unverified and are
                tagged with the file they came from.
- manual      - typed at the CLI. Verified.

Nothing here overwrites existing rows. Imports add, and every row records the
source it came from so a bad import can be undone wholesale.
"""

from . import documents, linkedin  # noqa: F401

__all__ = ["documents", "linkedin"]
