# Drop career material here

Anything that says something true about your work history. Then:

```bash
python -m jobsearch import inbox inbox/
```

**What to put in:**

- Your LinkedIn data export (`.zip`) — Settings → Data Privacy → Get a copy of your data
- Resumes and CVs, including old ones. Old versions hold accomplishments you've since
  cut for space; the graph has no page limit.
- Performance reviews and self-assessments — the best source of quantified impact,
  because someone made you write the numbers down at the time.
- Project write-ups, launch retros, design docs you led
- Certifications, transcripts, award letters
- Notes to yourself. A plain `.txt` of "things I did at $JOB that I keep forgetting"
  works fine.

Supported: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.html`, and `.zip` for
LinkedIn exports.

**After importing**, run `python -m jobsearch link` to attach skills to the records that
prove them, then `python -m jobsearch review` to confirm what the extractor pulled out.
Anything it got wrong: `python -m jobsearch rm experiences <id>`, or undo a whole file
with `python -m jobsearch sources undo <id>`.

Everything in this folder is gitignored — it's your personal data.
