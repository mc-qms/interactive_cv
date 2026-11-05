# Interactive CV v2 — Manuel Chavez

A governed LLM portfolio agent, built to the Resume Agent v2 spec
(Oct 30, 2026): Python owns what must be true, the LLM owns what
should feel human.

A visitor asks about Manuel's background. The LLM answers from a
structured dossier only, must cite the dossier field IDs it used,
and flags gaps instead of inventing. Python validates every answer
before display: citations must exist, and contact details, salary
figures, Python-authorship claims, and TrackWise / 820 / ISO 13485
presented as direct experience are blocked.

## Files

- `app.py` — the whole app: dossier, providers, validator, UI.
- `requirements.txt` — `streamlit` only. Provider calls use the
  Python standard library, so there are no other dependencies.
- `.devcontainer/` — optional. Only for local development in VS Code
  / Codespaces. Not needed for Streamlit Cloud.

## Deploy on Streamlit Cloud

1. Push this folder to a public GitHub repo.
2. In Streamlit Cloud, New app → pick the repo, branch, and
   `app.py` as the main file.
3. Settings → Secrets, add one key:
   - `GEMINI_API_KEY = "..."`, or
   - `ANTHROPIC_API_KEY = "..."`, or
   - `OPENAI_API_KEY = "..."`
4. Deploy. With no key, the app runs in Dossier Demo mode and
   says so — it never pretends an LLM is running.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

For a live model locally, set the key as an environment variable
or in `.streamlit/secrets.toml` — never commit a key to the repo.
