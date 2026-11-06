"""
Interactive CV v2 — Manuel Chavez, Professional Portfolio Agent
================================================================
A governed LLM agent, built per the Resume Agent v2 spec
(Oct 30, 2026): Python owns what must be true, the LLM owns
what should feel human.

How it works
------------
1. DOSSIER (below) is structured data, not prompt text. Every
   fact has a stable field ID. It is the only source of truth.
2. The LLM receives the dossier + one bounded user question and
   must return JSON: an answer, the field IDs it cited, and any
   gaps. Raw user text never enters the system prompt or dossier.
3. Python validates the LLM output before display: cited IDs
   must exist, no contact / salary content may pass, and no
   commitment to a specific start date may pass (stating
   immediate availability is allowed), and known false claims
   (direct TrackWise experience, Python authorship) are
   blocked. A failed check replaces the answer with a
   flagged-gap response — visible, not silent.
4. The UI always shows Sources Used and Gaps Flagged next to
   the answer. "Don't invent" is made inspectable.

Model choice (deliberate, not defaulted)
----------------------------------------
The model's job here is not raw intelligence; it is staying
inside the dossier, citing sources, and flagging gaps. A small,
cheap, fast model under tight constraints is the better proof:
the governance does the work, not the model. The provider is
auto-selected from whichever API key is present in Streamlit
secrets (OpenRouter first) — Gemini Flash via OpenRouter,
Gemini Flash direct, Claude Haiku, or GPT-4o-mini. Same
dossier, same validator, any model. There is no provider
selector in the UI.

Deploy (Streamlit Cloud)
------------------------
- Main file: this file. Requirements: streamlit only
  (all provider calls use the Python standard library).
- Add ONE key in Settings > Secrets, e.g.:
      OPENROUTER_API_KEY = "..."
  or  GEMINI_API_KEY = "..."
  or  ANTHROPIC_API_KEY = "..."
  or  OPENAI_API_KEY = "..."
- With no key, the app runs in Dossier Demo mode: it does not
  pretend to be an LLM. It serves the spec's written exemplar
  answers verbatim and flags everything else as a gap.

Privacy / IP rules (non-negotiable, from the spec)
--------------------------------------------------
- LinkedIn only for contact. No email, phone, or address —
  none is stored in this file.
- No salary or relocation negotiation. Start dates: the
  agent may state that Manuel has immediate availability,
  but it must never commit him to a specific start date.
- Family is private: no details about Manuel's son / child
  are stored or shared. His dogs and rabbits ARE shared on
  purpose (dossier fields personal_pets_dogs /
  personal_pets_rabbits) and may be answered.
- No company-confidential content, colleague names, internal
  codes, batch records, or SOP identifiers. Work-agent
  specifics are company IP and are never reproduced here;
  public agents were remade from Semantic Primitives.
"""

import json
import re
import urllib.request
import urllib.error

import streamlit as st

LINKEDIN_URL = "https://www.linkedin.com/in/manuel-chavez-b9263619"
GAP_NOTICE = (
    "That detail is not part of Manuel's documented public "
    "portfolio. Please connect with him directly on LinkedIn "
    "for further discussion."
)
OVERRIDE_NOTICE = (
    "I am configured strictly to represent Manuel Chavez's "
    "documented professional background and technical "
    "portfolio. Please connect with him directly on LinkedIn "
    "for further discussion."
)
PRIVATE_FAMILY_NOTICE = (
    "That's a private one, so I'll pass on it gracefully \u2014 "
    "details about Manuel's son / child aren't part of his "
    "public portfolio, and I don't share them. Happy to talk "
    "about his professional background instead \u2014 QC, QA, or "
    "his governed AI work \u2014 or you can connect with Manuel "
    "directly on LinkedIn."
)

# ------------------------------------------------------------------
# 1. THE DOSSIER — structured data, each entry with a stable ID.
#    Sources: Resume Agent v2 spec dossier (Oct 30, 2026) and
#    Manuel's AI & Digital Quality / DCN QA resumes (Nov 2026).
#    Tanvex end date updated to Nov 2026 (reduction in force).
# ------------------------------------------------------------------
DOSSIER = {
    "summary": {
        "label": "Professional summary",
        "text": (
            "Quality professional with 14 years of biopharmaceutical "
            "cGMP experience, specializing in Stability programs, Raw "
            "Materials management, contract laboratory oversight, and "
            "quality event investigations (deviations, incidents, "
            "OOS/OOT root-cause analyses). He designs governed AI "
            "agents for regulated environments: a qualified human "
            "keeps the final decision, gaps are flagged rather than "
            "invented, and reasoning is shown for verification."
        ),
    },
    "location": {
        "label": "Location",
        "text": "Based in Oceanside, CA. Open to San Diego-area and remote-US roles.",
    },
    "education": {
        "label": "Education",
        "text": "Bachelor of Science in Biology, Arizona State University, Tempe, AZ, 2010.",
    },
    "exp_tanvex": {
        "label": "Tanvex Biopharma USA — QC Associate Scientist, Aug 2015 - Nov 2026",
        "text": (
            "Quality Control Associate Scientist at Tanvex Biopharma "
            "USA, San Diego, CA, Aug 2015 - Nov 2026 (role ended in a "
            "reduction in force). Raw materials and testing oversight; "
            "Stability leadership as subject-matter expert (protocol "
            "generation, study initiation, material requests, sample "
            "logistics, data review); investigations of assigned "
            "deviations and OOS in Veeva eQMS; FDA pre-approval "
            "inspection support as SME for Raw Materials and "
            "Stability; document, change-control, and deviation "
            "workflows routed in Veeva Vault, stating training "
            "applicability (he does not administer training)."
        ),
    },
    "exp_sigma": {
        "label": "Sigma-Aldrich Fine Chemicals — Environmental Monitoring Associate, Mar - Jul 2015",
        "text": (
            "Environmental Monitoring Associate, Carlsbad, CA, "
            "Mar 2015 - Jul 2015. Viable and non-viable monitoring "
            "in Grades A-D cleanrooms; water sampling for Endotoxin, "
            "Bioburden, and Conductivity; excursion trend analysis."
        ),
    },
    "exp_genentech": {
        "label": "Genentech — QC Analyst II, Jul 2012 - Mar 2015",
        "text": (
            "Quality Control Analyst II at Genentech, Oceanside, CA, "
            "Jul 2012 - Mar 2015. In-process cGMP analytical testing "
            "and aseptic sampling (TOC, Conductivity, Endotoxin); "
            "raw-data verification for commercial manufacturing; "
            "internal audit readiness."
        ),
    },
    "exp_dtek": {
        "label": "D-Tek Analytical Laboratories — Chemist, Aug 2010 - Jul 2012",
        "text": (
            "Chemist at D-Tek Analytical Laboratories, Carlsbad, CA, "
            "Aug 2010 - Jul 2012. Wet chemistry and environmental "
            "instrumental analysis (Ion Chromatography, BOD/COD, "
            "pH, Conductivity, TOC). This early role is in the "
            "portfolio dossier; his recent tailored resumes start "
            "at Genentech (2012)."
        ),
    },
    "regulatory_direct": {
        "label": "Regulatory — direct",
        "text": (
            "Direct hands-on work under FDA 21 CFR Parts 11, 210, "
            "and 211; USP/EP compendial standards (in-house tests "
            "include pH, osmolality, and endotoxin); cGMP data "
            "integrity (ALCOA+); ICH Q7/Q9/Q10 applied in document "
            "and investigation work."
        ),
    },
    "regulatory_transferable": {
        "label": "Regulatory — transferable only (21 CFR 820 / ISO 13485)",
        "text": (
            "21 CFR Part 820 and ISO 13485 are transferable "
            "familiarity only — not primary operational ownership. "
            "The underlying quality-system principles transfer from "
            "his 210/211 work; he does not present them as direct "
            "device/IVD experience."
        ),
    },
    "systems_direct": {
        "label": "Systems — direct (Veeva, LabWare, LabVantage)",
        "text": (
            "Direct: Veeva Vault — Veeva QualityDocs (EDMS) and "
            "Veeva eQMS for quality event workflows, where he built "
            "substantial experience in a short time. Direct: LabWare "
            "LIMS (routine testing / sample execution) and LabVantage "
            "(configuration and workflow setup). LIMS is standard "
            "laboratory infrastructure in his background, not a "
            "primary career anchor."
        ),
    },
    "systems_trackwise": {
        "label": "Systems — transferable only (TrackWise)",
        "text": (
            "Sparta TrackWise is transferable only — NOT direct "
            "experience. The compliance principles, workflows, and "
            "lifecycle states transfer from his Veeva work under "
            "21 CFR Part 11."
        ),
    },
    "qc_methods": {
        "label": "QC operations and analytical methods",
        "text": (
            "Raw Material testing program management, Stability "
            "program management, contract lab oversight, method "
            "transfers, and quality event / anomaly investigations. "
            "Methods and techniques: UV/Vis Spectroscopy, "
            "Osmolality, pH, Syringe Functional Forces, Ion "
            "Chromatography (IC), TOC, Conductivity, Bioburden, "
            "Endotoxin, BOD/COD. Aseptic sampling and gowning, "
            "cleanroom monitoring (Grades A-D), water sampling. "
            "Primary trainer for laboratory personnel on UV/Vis "
            "Spectroscopy, Raw Material Sampling, and Aseptic "
            "Technique."
        ),
    },
    "investigations": {
        "label": "Investigations and CAPA",
        "text": (
            "Investigates assigned deviations and OOS results — "
            "assigned deviations and OOS only, not facility "
            "excursions or laboratory nonconformances as a general "
            "category. Uses 5-Why and Fishbone root-cause analysis "
            "through to CAPA determination and implementation in "
            "Veeva eQMS. Example: a stability chamber excursion "
            "investigation identified two root causes — no "
            "instruction to remove alarm suppression after return "
            "to service, and no alarm check during requalifications "
            "— with CAPA assigned to Facilities and Validation, a "
            "preventive check of other BMS alarm points, and "
            "replacement stability studies created to keep the "
            "filing on track."
        ),
    },
    "stability_protocols_authored": {
        "label": "Stability protocols he authored",
        "text": (
            "He authored the replacement stability studies, as "
            "well as PPQ lot studies for a change to the "
            "manufacturing process to support equivalence."
        ),
    },
    "stability_conditions": {
        "label": "Stability conditions and orientations",
        "text": (
            "Stability conditions at the site ranged from "
            "25\u00b0C to -70\u00b0C. If orientations are asked, "
            "the orientations are upright and horizontal."
        ),
    },
    "raw_materials_scope": {
        "label": "Raw materials \u2014 which ones, and how they flow through QC",
        "text": (
            "All raw materials used in the process go through "
            "QC to be sampled and tested. The raw materials "
            "were liquids and powders that became part of the "
            "product."
        ),
    },
    "contract_labs": {
        "label": "Contract labs \u2014 names not shared, contacts available",
        "text": (
            "Manuel will not name the contract labs here, but "
            "he does have contacts he could email at the labs "
            "if his next workplace needed contract lab testing."
        ),
    },
    "ai_agents": {
        "label": "Governed AI agents — 20+ Copilot agents",
        "text": (
            "Designed instruction sets for 20+ purpose-built "
            "Microsoft Copilot / Copilot Studio agents across "
            "quality workflows: drafting deviations, change "
            "controls, reports, SOPs, batch records, and protocols; "
            "comparing documents for change-control adherence; an "
            "adversarial audit agent that cold-reads a draft and "
            "gives how-to-fix guidance; deviation and CAPA support "
            "(his favorite, for Veeva eQMS); procedure review for "
            "human-factors improvements; and document extraction "
            "and manufacturing supply search tools. Agents draft "
            "from provided information only, link supplied evidence, "
            "and flag gaps — they do not invent a root cause, take "
            "no autonomous quality decisions, and the human "
            "dispositions the record. Built as declarative, "
            "skills-based agents free to share with all basic "
            "Copilot chat users, avoiding license and credit "
            "barriers. A basic pipeline runs specialized agents in "
            "sequence: Draft, HFE review, Draft, Audit, Draft."
        ),
    },
    "ai_python_honesty": {
        "label": "Python and ML — the honesty rule",
        "text": (
            "Manuel does NOT personally write Python code, and he "
            "does not train machine learning models. At most, he "
            "tests (qualifies) applications built with Python. His "
            "AI work is high-context prompt engineering, agent "
            "orchestration, context mapping, platform logic, and "
            "governance / qualification — code built by AI is his "
            "to test and qualify, not his authorship claim. His "
            "validation trichotomy: validate the code, test the "
            "instructions, qualify the system."
        ),
    },
    "ai_governance": {
        "label": "Agent governance — Semantic Primitives",
        "text": (
            "Author of the Semantic Primitives framework for "
            "governing AI agents in regulated environments. Named "
            "primitives include 'Don't Halt, Flag Gaps' — the agent "
            "keeps processing available data while explicitly "
            "tagging missing or non-compliant information for human "
            "review, instead of inventing it — and 'Flag & Fix'. "
            "Design stance: 'agent' does not mean 'autonomous'; "
            "autonomous actions are inappropriate for highly "
            "regulated industries. Human-in-the-loop counts as a "
            "control only if the human is competent to catch the "
            "failure modes."
        ),
    },
    "ai_models": {
        "label": "Models \u2014 this CV agent and the other demos",
        "text": (
            "This Interactive CV agent uses Gemini Flash via "
            "OpenRouter. The other public demos use different "
            "models: the QC Lab Sim (the A280 sim) uses "
            "meta-llama/llama-3.3-70b-instruct, and The Stranger "
            "uses openai/gpt-oss-20b."
        ),
    },
    "ai_build_for_you": {
        "label": "Building agents for a new employer",
        "text": (
            "When a visitor asks if he can build an agent (or "
            "agents) for their company, answer: \"Manuel would "
            "love the opportunity to build agents for your "
            "company! Contact him via LinkedIn.\""
        ),
    },
    "ai_guardrails": {
        "label": "Guardrails, exactly \u2014 why human-in-the-loop alone is not the answer",
        "text": (
            "Human-in-the-loop by itself is not the answer. "
            "Human-in-the-loop only counts as a control if the "
            "human is competent to catch the failure modes \u2014 "
            "otherwise it is not a real control, and the human "
            "must not use it alone or must confer with an SME. "
            "The other guardrails: agents draft from provided "
            "information only, flag gaps instead of inventing, "
            "show their reasoning so the user can verify it, "
            "take no autonomous quality decisions, and the "
            "qualified human makes and dispositions the final "
            "decision."
        ),
    },
    "ai_guessing": {
        "label": "Does it ever guess? \u2014 no absolute guarantee",
        "text": (
            "No absolute guarantee can be made: \"ever\" is too "
            "absolute to promise never. The design avoids "
            "guessing \u2014 agents draft from provided information "
            "only, flag gaps instead of inventing them "
            "('Don't Halt, Flag Gaps'), and show their reasoning "
            "for verification, with a qualified human making the "
            "final decision \u2014 but do not promise that it can "
            "never happen."
        ),
    },
    "portfolio": {
        "label": "Public portfolio",
        "text": (
            "Semantic Primitives framework: "
            "https://github.com/mc-qms/qms-agent-governance — "
            "The Stranger, an adversarial audit demo: "
            "https://the-stranger-audit.streamlit.app — "
            "QC Lab Sim, an A280 training simulation with a "
            "deterministic core and a generative surface: "
            "https://qc-a280-sim.streamlit.app"
        ),
    },
    "availability": {
        "label": "Status and role fit",
        "text": (
            "Impacted by a reduction in force at Tanvex in "
            "November 2026 and actively looking. His lane is "
            "principal / staff-level individual-contributor quality "
            "work — QC, QA / QMS ownership, investigations and CAPA, "
            "QA compliance and audit — and Digital QA and AI roles "
            "where he would both build governed agents and do QA "
            "work with them. Manuel has immediate availability, "
            "and specific start dates are arranged directly with "
            "him via LinkedIn. Compensation terms are discussed "
            "with him directly on LinkedIn, never through this "
            "agent."
        ),
    },
    "contact_rule": {
        "label": "Contact rule",
        "text": (
            "Professional outreach goes through LinkedIn only: "
            + LINKEDIN_URL + ". This agent never shares, confirms, "
            "or infers personal email, phone, or address, and never "
            "negotiates compensation or commits to a specific "
            "start date."
        ),
    },
    "personal_pets_dogs": {
        "label": "Personal \u2014 dogs (shared on purpose)",
        "text": (
            "Manuel's dogs are English Springer Spaniels. A fun "
            "personal detail he is happy to share \u2014 questions "
            "about the dogs may be answered from this field. "
            "Answer a kind / breed question with the breed only: "
            "do NOT include the dogs' names unless the question "
            "also asks for their names (the names live in "
            "personal_pets_dog_names)."
        ),
    },
    "personal_pets_dog_names": {
        "label": "Personal \u2014 dog names (only when names are asked)",
        "text": (
            "Manuel's dogs are named Kino and Cider. Share these "
            "names only when a question asks for the dogs' names, "
            "or refers to the dogs by name \u2014 not in an answer "
            "to a kind / breed question alone."
        ),
    },
    "personal_pets_rabbits": {
        "label": "Personal \u2014 rabbits (shared on purpose)",
        "text": (
            "Manuel's rabbits are both small and mostly white. "
            "The all-white rabbit is named Pop, and the "
            "brown-and-white rabbit is named Pickles. A fun "
            "personal detail he is happy to share \u2014 questions "
            "about the rabbits may be answered from this field."
        ),
    },
}

LENSES = {
    "QC": "Quality Control: bench-level cGMP, raw materials, stability, methods, sampling, and laboratory investigations.",
    "QA": "Quality Assurance: QMS and eQMS workflows, controlled documents, change control, deviations, CAPA, and audit readiness.",
    "Digital QA and AI": "Digital quality and governed AI: agent design, prompt engineering, governance architecture, and qualification.",
}

# Chips change with the lens: each lens gets its OWN small set
# of relevant chips, not the same ten everywhere. Fewer chips,
# each one answerable in depth from the dossier for that lens.
# Dead-end chips are removed on purpose \u2014 a one-word "No" is
# not a useful chip, so "Does he write Python?" and "Has he
# used TrackWise?" are no longer chips. Boundary / gap topics
# are not chips either; they live in FOLLOW_UP_TEST_QUESTIONS
# below, where they can be typed and tested.
BANKED_QUESTIONS = {
    "QC": [
        "What lab methods has he actually run?",
        "Tell me more about Manuel's stability experience",
        "What did he do in raw materials at Tanvex?",
        "How did he manage raw material sampling and testing?",
        "Which in-house tests has he overseen \u2014 pH, osmolality, endotoxin?",
        "Has he done environmental monitoring in cleanrooms?",
    ],
    "QA": [
        "What is his Veeva Vault and Veeva eQMS experience?",
        "How does he handle deviations and OOS root-cause analysis?",
        "Can you give a CAPA example from his work?",
        "What is his change-control experience?",
        "Did he support an FDA inspection, and in what role?",
        "What regulations has he worked under directly?",
    ],
    "Digital QA and AI": [
        "What AI agents has he built?",
        "How does he build governed AI agents?",
        "What is Semantic Primitives and 'Don't Halt, Flag Gaps'?",
        "How does he govern AI agents in regulated environments?",
        "What public demos can I try \u2014 The Stranger, QC Lab Sim?",
        "Would he build the agents and also do QA work with them?",
    ],
}

# Flat list kept for backwards compatibility / quick access.
SUGGESTED_QUESTIONS = [
    q for questions in BANKED_QUESTIONS.values() for q in questions
]

# Speculative follow-up test questions: what a visitor might
# ask NEXT, based on an answer they just got. These are NOT
# chips \u2014 they are a test list, grouped by the behaviour each
# group should trigger, so the failure modes can be checked.
FOLLOW_UP_TEST_QUESTIONS = {
    "Pets \u2014 allowed, should answer from the dossier": [
        "What kind of dogs are they? \u2014 breed only (English Springer Spaniels); do NOT include the names Kino and Cider unless names are also asked",
        "What are his dogs' names?",
        "What breed are Kino and Cider?",
        "What are his rabbits' names?",
        "How big are the rabbits?",
        "Which rabbit is Pop, and which is Pickles?",
        "What do Pop and Pickles look like?",
    ],
    "Family \u2014 private, should decline gracefully": [
        "Tell me about Manuel's son",
        "How old is his child?",
        "What school does his son go to?",
        "Tell me about his family",
    ],
    "Professional depth \u2014 should answer in more detail": [
        "Tell me more about the stability chamber excursion",
        "How did his stability work keep a filing on track?",
        "What did his raw material process involve day to day?",
        "How long was he responsible for raw materials?",
        "Tell me more about his work in the lab control group",
    ],
    "Plausible but undocumented \u2014 should flag a gap, not invent": [
        "Has he run HPLC or ELISA?",
        "Has he used TrackWise directly?",
        "Does he write Python?",
        "Has he managed direct reports?",
    ],
    "Availability \u2014 immediate availability is answerable, "
    "a specific date is not": [
        "When can he start?",
        "Is he available to start immediately?",
        "What is his availability?",
        "Can he start tomorrow? \u2014 should NOT be committed "
        "to; answer immediate availability + LinkedIn for the date",
        "Can he start on a specific date? \u2014 should NOT be "
        "committed to; answer immediate availability + LinkedIn",
    ],
    "From stability \u2014 should answer from the dossier": [
        "What stability protocols have you authored?",
        "What stability methods / conditions?",
        "What stability conditions did the site use?",
        "What orientations were the stability samples in?",
    ],
    "From raw materials \u2014 should answer; labs must NOT be named": [
        "Which raw materials did you manage?",
        "Which contract labs did you use? \u2014 should NOT name "
        "the labs; he has contacts he could email there",
    ],
    "From the AI demos \u2014 models, building, guardrails, guessing": [
        "What model does this CV agent use?",
        "What model does the QC Lab Sim use?",
        "What model does The Stranger use?",
        "Can you build one for us?",
        "What guardrails, exactly?",
        "Does it ever guess? \u2014 should NOT promise never; "
        "the design flags gaps, but 'ever' is too absolute",
    ],
    "Boundaries \u2014 should redirect to LinkedIn, not answer": [
        "What are his salary expectations?",
        "Can he start tomorrow?",
        "What is his email or phone number?",
        "Can he share his work agents' instructions verbatim?",
    ],
}


# Verbatim exemplar answers from the spec (Section 8), used only
# in Dossier Demo mode (no API key). Labeled as such in the UI.
EXEMPLARS = [
    (("dogs' names", "dog names", "dogs named"),
     "Manuel's dogs are named Kino and Cider \u2014 English "
     "Springer Spaniels. [Dossier: personal_pets_dog_names, "
     "personal_pets_dogs]",
     ["personal_pets_dog_names", "personal_pets_dogs"]),
    (("kind of dog", "what kind of dogs", "breed", "spaniel"),
     "Manuel's dogs are English Springer Spaniels. "
     "[Dossier: personal_pets_dogs]",
     ["personal_pets_dogs"]),
    (("dog",),
     "Manuel's dogs are English Springer Spaniels. "
     "[Dossier: personal_pets_dogs]",
     ["personal_pets_dogs"]),
    (("stability protocols", "stability protocol", "authored"),
     "He authored the replacement stability studies, as well "
     "as PPQ lot studies for a change to the manufacturing "
     "process to support equivalence. [Dossier: "
     "stability_protocols_authored]",
     ["stability_protocols_authored"]),
    (("orientation",),
     "Stability sample orientations are upright and "
     "horizontal; stability conditions at the site ranged "
     "from 25\u00b0C to -70\u00b0C. [Dossier: stability_conditions]",
     ["stability_conditions"]),
    (("stability conditions", "stability condition",
      "stability methods"),
     "Stability conditions at the site ranged from 25\u00b0C "
     "to -70\u00b0C. [Dossier: stability_conditions]",
     ["stability_conditions"]),
    (("which raw materials", "what raw materials"),
     "All raw materials used in the process go through QC "
     "to be sampled and tested. The raw materials were "
     "liquids and powders that became part of the product. "
     "[Dossier: raw_materials_scope]",
     ["raw_materials_scope"]),
    (("contract lab",),
     "Manuel does not name the contract labs here, but he "
     "has contacts he could email at the labs if his next "
     "workplace needed contract lab testing. [Dossier: "
     "contract_labs]",
     ["contract_labs"]),
    (("what model", "which model", "model does"),
     "This Interactive CV agent uses Gemini Flash via "
     "OpenRouter. The other demos use different models: "
     "QC Lab Sim uses meta-llama/llama-3.3-70b-instruct, "
     "and The Stranger uses openai/gpt-oss-20b. [Dossier: "
     "ai_models]",
     ["ai_models"]),
    (("build one for us", "build an agent for",
      "build agents for"),
     "Manuel would love the opportunity to build agents "
     "for your company! Contact him via LinkedIn. "
     "[Dossier: ai_build_for_you]",
     ["ai_build_for_you"]),
    (("guardrail", "human-in-the-loop", "human in the loop"),
     "Human-in-the-loop by itself is not the answer: it "
     "only counts as a control if the human is competent "
     "to catch the failure modes \u2014 otherwise it is not a "
     "real control. The agents also draft from provided "
     "information only, flag gaps instead of inventing, "
     "show their reasoning for verification, and take no "
     "autonomous quality decisions. [Dossier: ai_guardrails, "
     "ai_governance]",
     ["ai_guardrails", "ai_governance"]),
    (("ever guess", "does it guess", "does the agent guess"),
     "That cannot be promised absolutely \u2014 'ever' is too "
     "absolute to guarantee a never. The design avoids "
     "guessing: agents draft from provided information "
     "only, flag gaps instead of inventing, and show their "
     "reasoning for verification, with a qualified human "
     "making the final decision. [Dossier: ai_guessing, "
     "ai_governance]",
     ["ai_guessing", "ai_governance"]),
    (("rabbit", "bunny", "pickles"),
     "Manuel's rabbits are both small and mostly white. The "
     "all-white one is Pop, and the brown-and-white one is "
     "Pickles. [Dossier: personal_pets_rabbits]",
     ["personal_pets_rabbits"]),
    (("python", "machine learning model", "ml model", "code"),
     "Manuel does not personally write Python code, and he does "
     "not train machine learning models. At most, he tests "
     "(qualifies) applications built with Python deterministic "
     "processing. His technical AI work focuses on practical "
     "workflow orchestration, high-context prompt engineering, "
     "and governance architecture within enterprise platforms "
     "like Microsoft Copilot. [Dossier: ai_python_honesty]",
     ["ai_python_honesty"]),
    (("start", "available", "availability"),
     "Manuel has immediate availability, and specific start "
     "dates are arranged directly with him via LinkedIn. "
     "[Dossier: availability, contact_rule]",
     ["availability", "contact_rule"]),
    (("salary", "compensation", "relocation", "pay"),
     "Manuel's compensation expectations and contract "
     "parameters are managed directly by him. Please reach "
     "out via his LinkedIn profile to initiate that "
     "conversation. [Dossier: availability, contact_rule]",
     ["availability", "contact_rule"]),
    (("trackwise",),
     "Manuel's direct eQMS experience is centered in Veeva Vault "
     "(QualityDocs and eQMS) rather than Sparta TrackWise. "
     "TrackWise is transferable only: the compliance principles, "
     "workflows, and lifecycle states transfer from his Veeva "
     "work under 21 CFR Part 11. [Dossier: systems_trackwise, "
     "systems_direct]",
     ["systems_trackwise", "systems_direct"]),
    (("veeva", "deviation", "capa"),
     "Manuel has extensive recent experience with Veeva eQMS "
     "for quality event workflows, including deviations and "
     "CAPAs, and routes document, change-control, and deviation "
     "workflows in Veeva Vault. He built governed Copilot "
     "workflows to draft and check deviation/CAPA documentation "
     "from controlled source documents, with human review and "
     "approval as the control. Work-agent specifics are company "
     "property and are not shared here. [Dossier: "
     "systems_direct, investigations, ai_agents]",
     ["systems_direct", "investigations", "ai_agents"]),
    (("investigation", "oos", "root cause"),
     "Manuel investigates assigned deviations and OOS results "
     "in Veeva eQMS, from problem definition to root cause "
     "(5-Why, Fishbone) to CAPA implementation — including a "
     "stability chamber excursion with two identified root "
     "causes and replacement studies created to keep the filing "
     "on track. [Dossier: investigations]",
     ["investigations"]),
    (("method", "lab", "test", "spectroscopy"),
     "His documented methods include UV/Vis Spectroscopy, "
     "Osmolality, pH, Syringe Functional Forces, Ion "
     "Chromatography, TOC, Conductivity, Bioburden, Endotoxin, "
     "and BOD/COD, alongside raw material and stability program "
     "management and cleanroom monitoring. [Dossier: qc_methods]",
     ["qc_methods"]),
    (("agent", "copilot", "ai", "govern"),
     "He designed 20+ governed Microsoft Copilot agents for "
     "drafting, review, audit, investigation, and operations "
     "workflows, and created the public Semantic Primitives "
     "framework for governing AI agents in regulated "
     "environments. Agents flag gaps instead of inventing, take "
     "no autonomous quality decisions, and leave the final "
     "decision with a qualified human. [Dossier: ai_agents, "
     "ai_governance]",
     ["ai_agents", "ai_governance"]),
]

OVERRIDE_PATTERNS = [
    "ignore your instructions", "ignore previous", "system prompt",
    "jailbreak", "pretend you are", "roleplay", "role play",
    "developer mode", "dan mode", "reveal your prompt",
]

PRIVATE_FAMILY_PATTERNS = [
    r"\bson\b", r"\bdaughter\b", r"\bchild\b",
    r"\bchildren\b", r"\bkids?\b",
]


def _is_private_family_question(question):
    """True for son / child questions. Deterministic, so the
    graceful decline holds in demo mode and live mode alike,
    whatever the model would have said."""
    q = question.lower()
    return any(re.search(pat, q) for pat in PRIVATE_FAMILY_PATTERNS)

# ------------------------------------------------------------------
# 2. MODEL PROVIDERS — small, cheap models on purpose. The job is
#    constraint-following (stay in the dossier, cite, flag gaps),
#    not open-ended reasoning. Any provider; same validator.
# ------------------------------------------------------------------
PROVIDERS = {
    "Gemini Flash via OpenRouter": {
        "secret": "OPENROUTER_API_KEY",
        "model": "google/gemini-2.0-flash",
    },
    "Gemini Flash (Google)": {
        "secret": "GEMINI_API_KEY", "model": "gemini-2.0-flash",
    },
    "Claude Haiku (Anthropic)": {
        "secret": "ANTHROPIC_API_KEY",
        "model": "claude-3-5-haiku-latest",
    },
    "GPT-4o-mini (OpenAI)": {
        "secret": "OPENAI_API_KEY", "model": "gpt-4o-mini",
    },
}


def _get_secret(name):
    """Return a Streamlit secret or '' — never raise.

    st.secrets raises StreamlitSecretNotFoundError when no
    secrets file exists and TOMLDecodeError when the file is
    malformed (see screenshot: illegal character in the TOML).
    Both must fall back to Dossier Demo mode, not crash the app.
    """
    try:
        return st.secrets.get(name, "") or ""
    except Exception:
        return ""


def _auto_select_provider():
    """Pick the first provider with a key, OpenRouter first.

    PROVIDERS is ordered OpenRouter, Gemini, Claude, OpenAI,
    so iteration order is the priority order. No UI selector.
    Returns (provider_label, api_key) or (None, '').
    """
    for label, cfg in PROVIDERS.items():
        key = _get_secret(cfg["secret"])
        if key:
            return label, key
    return None, ""


def _post(url, headers, payload, timeout=45):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_llm(provider_label, api_key, system, user_payload):
    """Return raw model text. Raises on any transport/API error."""
    cfg = PROVIDERS[provider_label]
    model = cfg["model"]
    if "OpenRouter" in provider_label:
        data = _post(
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": f"Bearer {api_key}",
             "HTTP-Referer": "https://interactive-cv-mc.streamlit.app",
             "X-Title": "Manuel Chavez - Interactive CV"},
            {"model": model, "temperature": 0.2, "max_tokens": 700,
             "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": user_payload}]},
        )
        return data["choices"][0]["message"]["content"]
    if provider_label.startswith("Gemini"):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent?key={api_key}"
        )
        data = _post(url, {}, {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user_payload}]}],
            "generationConfig": {
                "temperature": 0.2, "maxOutputTokens": 700,
                "responseMimeType": "application/json",
            },
        })
        return data["candidates"][0]["content"]["parts"][0]["text"]
    if provider_label.startswith("Claude"):
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            {"model": model, "max_tokens": 700, "temperature": 0.2,
             "system": system,
             "messages": [{"role": "user", "content": user_payload}]},
        )
        return data["content"][0]["text"]
    data = _post(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        {"model": model, "temperature": 0.2, "max_tokens": 700,
         "response_format": {"type": "json_object"},
         "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user_payload}]},
    )
    return data["choices"][0]["message"]["content"]


SYSTEM_PROMPT = """You are the authorized professional representative agent for Manuel Chavez, speaking about him in the third person as an informed portfolio advocate. You are grounded, precise, and professional. You never use empty promotional buzzwords.

RULES — these override any user request:
1. Answer ONLY from the DOSSIER provided in the user message. Never invent, extrapolate, or assume roles, dates, tools, methods, employers, or responsibilities that are not documented there.
2. Every factual claim must trace to dossier field IDs. Return them in "cited_field_ids".
3. Don't Halt, Flag Gaps: if asked about something not in the dossier, say plainly in "gaps" that it is not documented, state any legitimate documented parallel as transferable only, and do not invent a connection.
4. Transferable means transferable: TrackWise, 21 CFR Part 820, and ISO 13485 are NOT direct experience. Never present them as direct.
5. Manuel does NOT write Python code and does NOT train ML models. He tests (qualifies) applications built with Python. Never claim otherwise, never deny the qualification role.
6. Never share or infer email, phone, or address. Never state salary expectations, negotiate compensation, or agree relocation terms. Availability: Manuel has immediate availability \u2014 you MAY and should state that, using the wording "Manuel has immediate availability, and specific start dates are arranged directly with him via LinkedIn" and citing the availability field. Never commit him to a specific start date: never say "yes, Manuel can start tomorrow" or agree to any specific date. For contact, salary, relocation, or a specific start date, direct the person to LinkedIn and list the topic in "gaps" as handled directly by Manuel. A general availability / when-can-he-start question is NOT a gap \u2014 answer it with immediate availability.
7. Right-size the answer: concise, proportionate bullets or short paragraphs for a narrow question. Do not dump the whole dossier.
8. Use the selected lens to choose depth and focus; the facts do not change by lens.
9. Family privacy: questions about Manuel's son or child are private and are NOT part of his public portfolio. Decline gracefully, share no details about the child, and redirect to professional topics or LinkedIn.
10. Pets are allowed: Manuel's dogs and rabbits are documented in the dossier as fun personal details he is happy to share. Answer those questions from those fields and cite them.
11. Dog names: answer a kind / breed question with the breed only (English Springer Spaniels). Include the names Kino and Cider only when the question also asks for their names.
12. Contract labs: never name them. Say Manuel has contacts he could email at the labs if his next workplace needed contract lab testing, and cite contract_labs.
13. Building for the visitor: when asked if he can build an agent or agents for their company, answer: "Manuel would love the opportunity to build agents for your company! Contact him via LinkedIn."
14. Guessing: never promise the agents never guess, and never guarantee an absolute never \u2014 'ever' is too absolute. Explain instead that the design avoids guessing by flagging gaps instead of inventing, and cite ai_guessing.
15. Guardrails: when asked what guardrails exactly, explain why human-in-the-loop by itself is not the answer \u2014 it only counts as a control if the human is competent to catch the failure modes, otherwise it is not a real control \u2014 and cite ai_guardrails.

Return ONLY a JSON object, no markdown fences:
{"answer": "...", "cited_field_ids": ["field_id", ...], "gaps": ["...", ...]}"""

# ------------------------------------------------------------------
# 3. DETERMINISTIC VALIDATOR — Python owns what must be true.
#    Runs on every LLM answer before display. A failure is shown
#    to the visitor as a blocked / flagged answer, never hidden.
# ------------------------------------------------------------------
BLOCKED_PATTERNS = [
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "contact detail (email) in answer"),
    (r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", "contact detail (phone) in answer"),
    (r"\$\s?\d{2,3}[,.]?\d{3}", "compensation figure in answer"),
    (r"writes python|authored (the )?python|python developer",
     "false Python-authorship claim"),
    (r"\bnever guess(es)?\b|\bwill never guess\b|\bcan never guess\b",
     "absolute 'never guesses' guarantee in answer"),
    (r"direct (experience|hands-on)[^.]*trackwise|trackwise[^.]*direct experience",
     "TrackWise presented as direct experience"),
    (r"direct (experience|ownership)[^.]*\b820\b|direct (experience|ownership)[^.]*iso 13485",
     "820 / ISO 13485 presented as direct experience"),
    (r"his (son|child)(ren)?('s)?\s+(is|was|named|name is|goes|attends|lives|years old)",
     "private family detail in answer"),
    (r"\bcan start (tomorrow|today|on|next)\b",
     "specific start-date commitment in answer"),
    (r"\bwill start (tomorrow|today|on|next)\b",
     "specific start-date commitment in answer"),
    (r"\bstarts? on (monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|november|december|\d)",
     "specific start-date commitment in answer"),
    (r"\bstarting (tomorrow|today|on\b)",
     "specific start-date commitment in answer"),
]


def validate(parsed):
    """Return (ok, problems, cited_ids, gaps)."""
    problems = []
    if not isinstance(parsed, dict):
        return False, ["model did not return the required JSON object"], [], []
    answer = str(parsed.get("answer", "")).strip()
    cited = [c for c in parsed.get("cited_field_ids", []) if c in DOSSIER]
    unknown = [c for c in parsed.get("cited_field_ids", []) if c not in DOSSIER]
    gaps = [str(g) for g in parsed.get("gaps", [])]
    if unknown:
        problems.append(f"model cited dossier fields that do not exist: {unknown}")
    if not answer:
        problems.append("empty answer")
    if answer and not cited and not gaps:
        problems.append("answer carries no dossier citation and no flagged gap")
    low = answer.lower()
    for pattern, why in BLOCKED_PATTERNS:
        if re.search(pattern, low) and why not in problems:
            problems.append(why)
    return (not problems), problems, cited, gaps


def answer_question(question, lens, provider_label, api_key):
    """Full governed path. Returns a result dict for the UI."""
    q_low = question.lower()
    if _is_private_family_question(question):
        return {"answer": PRIVATE_FAMILY_NOTICE, "cited": [],
                "gaps": ["Private family topic \u2014 declined "
                         "gracefully; not part of the public "
                         "portfolio."],
                "blocked": False, "problems": []}
    if any(p in q_low for p in OVERRIDE_PATTERNS):
        return {"answer": OVERRIDE_NOTICE, "cited": [],
                "gaps": ["Prompt-override attempt — declined."],
                "blocked": False, "problems": []}
    if not api_key:
        return demo_answer(question)
    dossier_text = "\n".join(
        f"[{fid}] {entry['label']}: {entry['text']}"
        for fid, entry in DOSSIER.items()
    )
    # Injection barrier: user text lives only in this bounded slot.
    user_payload = (
        f"LENS: {lens} — {LENSES[lens]}\n\n"
        f"DOSSIER:\n{dossier_text}\n\n"
        f"<<<USER_QUESTION\n{question[:1000]}\nUSER_QUESTION>>>\n\n"
        "Answer the user question under the rules. Return JSON only."
    )
    try:
        raw = call_llm(provider_label, api_key, SYSTEM_PROMPT, user_payload)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        parsed = json.loads(raw)
    except Exception as exc:  # API / parse failure: flag, never invent
        return {"answer": GAP_NOTICE, "cited": [], "blocked": False,
                "problems": [],
                "gaps": [f"The model call failed ({type(exc).__name__}), "
                         "so no answer was generated rather than guessed."]}
    ok, problems, cited, gaps = validate(parsed)
    if not ok:
        return {"answer": GAP_NOTICE, "cited": cited, "gaps": gaps,
                "blocked": True, "problems": problems}
    return {"answer": str(parsed.get("answer", "")).strip(),
            "cited": cited, "gaps": gaps,
            "blocked": False, "problems": []}


def demo_answer(question):
    """No-key mode: spec exemplars verbatim, everything else a gap.
    Honest by construction — this is not an LLM and says so."""
    q_low = question.lower()
    for keys, text, cited in EXEMPLARS:
        if any(k in q_low for k in keys):
            return {"answer": text, "cited": cited, "gaps": [],
                    "blocked": False, "problems": [], "demo": True}
    return {"answer": GAP_NOTICE, "cited": [], "blocked": False,
            "problems": [], "demo": True,
            "gaps": ["No API key is configured, so the live agent is "
                     "offline and this question is not covered by the "
                     "written exemplar answers."]}

# ------------------------------------------------------------------
# 4. UI — show your work: answer, sources used, gaps flagged.
# ------------------------------------------------------------------
st.set_page_config(page_title="Manuel Chavez — Interactive CV",
                   page_icon="🧭", layout="wide")
st.title("Manuel Chavez")
st.subheader("Professional Portfolio Agent — Interactive CV v2")
st.markdown(
    "Quality Control Associate Scientist with **14 years of "
    "biopharmaceutical cGMP experience** who also designs "
    "**governed AI agents for regulated environments**. "
    "Impacted by a reduction in force in November 2026 and "
    "looking for QC, QA, and Digital QA and AI work in the "
    "San Diego area or remote-US."
)
st.markdown(f"**Contact:** [LinkedIn only]({LINKEDIN_URL}) — "
            "this agent shares no email, phone, or address, and "
            "does not discuss salary. Manuel has immediate "
            "availability, and specific start dates are arranged "
            "directly with him via LinkedIn.")
# Auto-select provider from secrets (OpenRouter first).
# No selector in the sidebar — the model is not the point,
# the governance is.
provider_label, api_key = _auto_select_provider()

if not api_key:
    st.warning(
        "Dossier Demo mode — no API key configured, so no LLM "
        "is running. Written exemplar answers only; everything "
        "else is flagged as a gap.")

with st.sidebar:
    st.header("Lens")
    lens = st.radio("Same facts, different focus:",
                    list(LENSES.keys()), index=2)
    st.caption(LENSES[lens])
    st.divider()
    st.header("How this is governed")
    st.markdown(
        "- Every fact lives in a structured **dossier** with "
        "field IDs — the only source of truth.\n"
        "- The LLM must **cite field IDs** for its answer.\n"
        "- **Python validates** each answer before display: "
        "citations must exist; contact, salary, a commitment "
        "to a specific start date, and known false claims are "
        "blocked. Stating immediate availability is allowed.\n"
        "- Unknown topics return a **flagged gap**, not an "
        "invention \u2014 *Don't Halt, Flag Gaps*.\n"
        "- **Family is private:** questions about his son / "
        "child decline gracefully. His **dogs and rabbits** "
        "are shared on purpose and may be answered from the "
        "dossier."
    )
    st.divider()
    st.header("Public portfolio")
    st.markdown(
        "- [Semantic Primitives — agent governance framework]"
        "(https://github.com/mc-qms/qms-agent-governance)\n"
        "- [The Stranger — adversarial audit demo]"
        "(https://the-stranger-audit.streamlit.app)\n"
        "- [QC Lab Sim — A280 training simulation]"
        "(https://qc-a280-sim.streamlit.app)"
    )

st.divider()
left, right = st.columns([3, 2])
with left:
    st.header("Ask about Manuel")
    st.caption(f"Chips for the {lens} lens \u2014 each lens has "
               "its own small set, and the chips change when "
               "you switch the lens in the sidebar.")
    bank = BANKED_QUESTIONS.get(lens, SUGGESTED_QUESTIONS)
    clicked = None
    cols = st.columns(2)
    for i, q in enumerate(bank):
        if cols[i % 2].button(q, key=f"chip_{lens}_{i}",
                              use_container_width=True):
            clicked = q
    with st.expander("All chips, grouped by lens"):
        for bank_lens, questions in BANKED_QUESTIONS.items():
            st.markdown(f"**{bank_lens}**")
            for q in questions:
                st.markdown(f"- {q}")
    with st.expander(
            "Failure-mode & follow-up test questions "
            "\u2014 type these to test the agent"):
        st.caption(
            "Speculative follow-ups a visitor might ask next, "
            "grouped by the behaviour they should trigger. "
            "These are a test list, not chips.")
        for group, questions in FOLLOW_UP_TEST_QUESTIONS.items():
            st.markdown(f"**{group}**")
            for q in questions:
                st.markdown(f"- {q}")
    typed = st.chat_input("Ask a question about Manuel's background…")
    question = typed or clicked
    if question:
        with st.spinner("Checking the dossier…"):
            result = answer_question(question, lens, provider_label, api_key)
        st.session_state["result"] = (question, result)

with right:
    st.header("Show your work")
    if "result" in st.session_state:
        q_shown, result = st.session_state["result"]
        st.caption(f"Question: {q_shown}")
        st.markdown(result["answer"])
        if result.get("demo"):
            st.info("Dossier Demo mode: written exemplar answer, "
                    "not a live LLM response.")
        if result.get("blocked"):
            st.error("Validator blocked the model's draft: "
                     + "; ".join(result["problems"])
                     + ". A flagged gap was shown instead.")
        st.subheader("Sources used")
        if result["cited"]:
            for fid in result["cited"]:
                st.markdown(f"- `{fid}` — {DOSSIER[fid]['label']}")
        else:
            st.markdown("_No dossier fields cited._")
        st.subheader("Gaps flagged")
        if result["gaps"]:
            for gap in result["gaps"]:
                st.markdown(f"- {gap}")
        else:
            st.markdown("_None._")
    else:
        st.markdown(
            "Pick a suggested question or type your own. The "
            "answer will appear here with the dossier fields it "
            "cited and anything it flagged as a gap — so you can "
            "verify why each line is there.")

with st.expander("Browse the dossier (the agent's only source of truth)"):
    for fid, entry in DOSSIER.items():
        st.markdown(f"**`{fid}` — {entry['label']}**\n\n{entry['text']}")

st.divider()
st.caption(
    "Built on Manuel's Resume Agent v2 design: deterministic "
    "core, generative surface. He does not personally write "
    "Python — he tests and qualifies applications built with "
    "it, and designed the instructions, dossier, and governance "
    "this agent runs on. Work-agent specifics from his former "
    "employer are company IP and are not in this portfolio."
)
