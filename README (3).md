# HomeFix AI

**Tell us what's wrong. We'll help you find the right professional.**

A conversational assistant for booking home repair services. Describe a
household problem in plain language; the app works out which trade you need,
ranks suitable professionals with a visible reason for each, and records the
request.

Built as a student project combining generative AI with business analytics.

> **All provider data in this project is fictional.** The 32 professionals,
> their ratings, prices, availability and phone numbers were invented for an
> academic demonstration. Submitting a request does not contact anyone.

---

## 1. Project overview

Finding a tradesperson usually means knowing what kind of tradesperson you
need. Someone whose ceiling is dripping may not know whether that is a
plumbing job, a roofing job or an air-conditioning drainage fault, and picking
wrong wastes a call-out fee.

HomeFix AI removes that step. The customer describes the symptom; a language
model turns the description into a structured summary; the application maps
that to one of eight service categories and ranks providers from a database.

The design principle throughout: **the language model handles language, and
the application handles facts.** The model never sees the provider list,
never quotes a price, and never confirms a booking. Everything a customer is
told about a professional comes from `providers.csv` via ordinary Pandas
operations that can be checked by hand.

---

## 2. Features

**Conversational intake.** Describe the problem in your own words, including
informal or misspelled English. The assistant asks at most one follow-up
question per turn, and only when the missing detail changes which
professional is needed.

**Controlled service classification.** Problems map to one of eight fixed
categories. The model cannot invent a ninth.

**Transparent provider ranking.** Each professional is scored out of 100 and
every card shows its own breakdown, so you can see exactly why one ranked
above another.

**Safety guard.** Gas leaks, fires, electric shocks, injuries and flooding are
detected before any API call and answered with emergency guidance, not
booking suggestions. Requests for do-it-yourself instructions on hazardous
work are declined.

**Knowledge base retrieval.** Questions about working hours, cancellations,
pricing policy, guarantees and coverage are answered from a knowledge base
rather than from the model's assumptions, and the app says when it does not
know.

**Booking and dashboard.** Submit a request, get a reference number, and see
it appear on the dashboard immediately.

**Business analytics.** Request volumes, busiest trade and area, average job
value, status distribution, weekly demand, and value by trade — with written
observations, not just charts.

**Works without an API key.** If Groq is unreachable, keyword classification
takes over and every other feature keeps working. The interface says which
path was used rather than pretending.

---

## 3. Architecture

```
                         ┌────────────────────────────┐
                         │   GRADIO UI (app.py)       │
                         │   6 tabs + gr.State        │
                         └────────────┬───────────────┘
                                      │
                         ┌────────────▼───────────────┐
                         │  src/ui_logic.py           │
                         │  pure logic, no Gradio     │
                         └────────────┬───────────────┘
                                      │
     ┌───────────┬──────────┬─────────┼─────────┬──────────┬───────────┐
     ▼           ▼          ▼         ▼         ▼          ▼           ▼
 ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌─────────┐
 │ safety │ │    ai_   │ │classif-│ │provi-│ │  rag   │ │databa- │ │analytics│
 │        │ │assistant │ │  ier   │ │ der_ │ │        │ │  se    │ │         │
 └────────┘ └────┬─────┘ └───┬────┘ │match-│ └───┬────┘ └───┬────┘ └────┬────┘
                 │           │      │ ing  │     │          │           │
                 ▼           ▼      └──┬───┘     ▼          ▼           ▼
            ┌─────────┐ ┌──────────┐   │   ┌──────────┐ ┌────────┐ ┌────────┐
            │Groq API │ │services  │   │   │knowledge │ │provid- │ │requests│
            │         │ │  .csv    │   └──►│ _base/   │ │ers.csv │ │  .csv  │
            └─────────┘ └──────────┘       └──────────┘ └────────┘ └────────┘
```

Everything imports from `src/config.py`, which imports from nothing in the
project, so circular imports are structurally impossible.

### One turn, end to end

```
user message
   │
   ▼
safety.screen()              keyword scan, before any API call
   │
   ├── critical hazard? ───►  emergency guidance, LLM never called, no cards
   │
   ▼
rag.is_policy_question()     is this about the service, or a broken thing?
   │
   ├── policy ──► rag.retrieve() ──► passages appended to the system prompt
   │
   ▼
ai_assistant.extract_request_info()    Groq, JSON mode, retry then fallback model
   │
   ▼
harden_slots()               nothing the model returns is trusted as-is
   │
   ▼
classifier.resolve()         validate against the 8 categories, or keyword fallback
   │
   ▼
provider_matching.find_providers()     hard filter, then score out of 100
   │
   ▼
ranked cards + score breakdown ──► booking ──► requests.csv ──► dashboard
```

---

## 4. Technologies

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | |
| Interface | Gradio 5 | Tabs, chat and charts with no front-end build step |
| Language model | Groq, `llama-3.3-70b-versatile` | Free tier, JSON mode, fast |
| Fallback model | `llama-3.1-8b-instant` | Separate rate-limit headroom |
| Data | Pandas + CSV | Inspectable, and gradeable by a human |
| Retrieval | sentence-transformers, or scikit-learn TF-IDF | No vector database needed |
| Secrets | Colab Secrets or python-dotenv | Same code runs in both places |

No paid APIs. No vector database. No front-end framework.

---

## 5. Folder structure

```
homefix_ai/
├── app.py                    Gradio interface: layout and event wiring only
├── generate_data.py          creates the three CSV files
├── run_all_tests.py          runs every test suite
├── requirements.txt
├── .env.example
│
├── src/
│   ├── config.py             paths, categories, weights, API key
│   ├── utils.py              IDs, masking, formatting, form validation
│   ├── safety.py             three-tier hazard guard
│   ├── ai_assistant.py       Groq client, system prompt, slot hardening
│   ├── classifier.py         category validation and keyword fallback
│   ├── provider_matching.py  the scoring engine
│   ├── rag.py                knowledge base retrieval
│   ├── database.py           the only module that touches the CSVs
│   ├── analytics.py          dashboard metrics and chart data
│   └── ui_logic.py           UI behaviour, no Gradio import
│
├── data/
│   ├── providers.csv         32 fictional professionals
│   ├── services.csv          the 8 categories and their keywords
│   └── requests.csv          bookings, created at runtime
│
├── knowledge_base/
│   ├── services.txt          what each trade covers
│   ├── faq.txt               common customer questions
│   └── policies.txt          hours, cancellation, guarantee, privacy
│
├── assets/style.css
├── cache/                    generated embeddings
└── test_stage3.py … test_stage12.py
```

---

## 6. Installation

### Google Colab

```python
!pip -q install gradio groq python-dotenv sentence-transformers

from google.colab import drive
drive.mount('/content/drive')

import os
BASE = '/content/drive/MyDrive/homefix_ai'
os.chdir(BASE)

import sys
sys.path.append(BASE)
%load_ext autoreload
%autoreload 2
```

Do not reinstall pandas, numpy, scikit-learn or matplotlib — Colab already has
them, and reinstalling is a reliable way to break the runtime.

Mounting Drive matters: without it, Colab deletes your bookings when the
session ends. `config.py` detects this and the app warns you.

### Local, VS Code

```bash
git clone <your-repo> && cd homefix_ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python generate_data.py
python app.py
```

---

## 7. Environment variables

One variable, `GROQ_API_KEY`, obtained free from `console.groq.com`.

**Colab:** left sidebar → key icon → **Secrets** → Add new secret → name it
`GROQ_API_KEY`, paste the value, and turn **Notebook access** on.

**Local:** create a `.env` file beside `app.py`:

```
GROQ_API_KEY=your_key_here
```

`.env.example` shows the expected shape. `.env` is in `.gitignore` — never
commit a real key.

`config.get_api_key()` tries Colab Secrets, then `.env`, then the environment,
and returns `None` if none of them work. The app launches either way and says
so in the banner.

---

## 8. How to run

```bash
python generate_data.py          # once, to create the CSVs
python app.py                    # launches with a public share link
```

In a notebook:

```python
from app import demo
demo.launch(share=True, debug=True)
```

Health checks, in order of usefulness:

```bash
python -m src.config            # paths, categories, whether a key was found
python -m src.ai_assistant      # live Groq call and two real extractions
python -m src.classifier        # the eight worked examples, scored
python -m src.provider_matching # three ranked searches
python -m src.rag               # which retrieval backend is active
python run_all_tests.py         # every suite: 1005 tests
```

---

## 9. Example questions

**Service problems**

- My AC is leaking water and isn't cooling
- kitchen sink blocked water not going down
- My washing machine is making a strange noise
- my lights keep going off in the lounge
- I need someone to paint my bedroom
- my cupboard door hinge is broken
- locked out, key broke in the lock

**Questions about the service** (answered from the knowledge base)

- what are your working hours
- can I cancel my booking
- do you work on Sundays
- is there a warranty on the repair
- which areas do you cover

**Safety** (answered with guidance, not bookings)

- there is a gas smell in my kitchen
- the socket is sparking and there's a burning smell
- how do I repair exposed electrical wiring myself

---

## 10. How AI classification works

The model receives a system prompt generated from `services.csv`, so the
prompt, the validator and the dataset can never disagree. It returns a single
JSON object using Groq's JSON mode:

```json
{
  "service_category": "AC Technician",
  "problem_summary": "AC leaking water and not cooling",
  "symptoms": ["leaking", "no cooling"],
  "urgency": "urgent",
  "area": "Islamabad",
  "follow_up_question": null,
  "reply": "That sounds like a drainage issue. Let me find an AC technician.",
  "confidence": 0.94
}
```

One call returns both the structured data and the conversational reply. Two
calls would cost twice as much and let the reply drift out of sync with the
extraction.

**Nothing in that response is trusted.** `harden_slots()` coerces, clamps or
discards every field:

| Model returns | Stored as |
|---|---|
| `"Pipe Guy"` | `None`, and the keyword fallback is flagged |
| `"ac technician"` | `"AC Technician"` |
| `"SUPER URGENT!!"` | `"normal"` |
| `confidence: 5` | `1.0` |
| `area: "pindi"` | `"Rawalpindi"` |
| `preferred_date: "next Tuesday"` | `None` |
| unexpected extra keys | discarded |

**When the model is unavailable**, `classifier.py` scores the raw text against
the keyword columns in `services.csv`. Two columns, weighted differently:

- `anchor_keywords` — the device or thing — **10 points per word**
- `keywords` — symptoms and context — **2 points per word**

Symptoms are ambiguous; objects are not. In *"my washing machine is leaking
water"*, "leaking" and "water" are Plumber words, but the washing machine
decides the trade. A flat keyword count gets this wrong.

The classifier refuses to guess: below a minimum score it returns nothing, and
when the top two categories are within 75% of each other it asks *"is this
more of an electrician job or a plumber job?"* instead of picking.

The interface always shows which path was used — model, keyword fallback, or
safety guard.

---

## 11. How provider matching works

**The trade is a hard filter, not a score.** A plumber is never offered for an
AC fault, however good their rating. Non-matching trades are removed before
any scoring.

Everyone remaining is scored out of 100:

| Factor | Weight | How |
|---|---|---|
| Area | 30 | exact 30, same region 15, elsewhere 0 |
| Rating | 30 | `rating ÷ 5 × 30` |
| Availability | 20 | urgent jobs: Today 20, Tomorrow 10, Weekends 0. Non-urgent: 15 for everyone |
| Price | 20 | full marks inside budget, scaled by overshoot, 0 above it |

Two decisions worth understanding:

**Area is a weight, not a filter.** Only one AC technician in the demo data is
based in Islamabad. Filtering on area would show a single card where the
customer expects a choice, so all four are scored and the local one comes
first.

**Neutral credit.** When a factor does not apply — no budget given, or the job
is not urgent — everyone receives 75% of that weight rather than zero.
Mathematically equivalent for ranking, but it stops a perfectly good
professional displaying as 62/100, which customers read as "bad".

Every card shows its own arithmetic:

| Factor | Points | Why |
| --- | --- | --- |
| Area | 30.0 / 30 | based in Islamabad |
| Rating | 27.6 / 30 | 4.6 out of 5 |
| Availability | 20.0 / 20 | available today |
| Price | 15.0 / 20 | no budget set |
| **Total** | **92.6 / 100** | |

---

## 12. How RAG works

**Used for:** questions about the service — working hours, cancellations,
pricing policy, guarantees, coverage.

**Not used for:** finding or filtering providers. That is structured data with
exact fields; *"which plumbers are free today in Lahore"* is a DataFrame
query. Similarity search there would be slower, less accurate and impossible
to explain. Using retrieval because it is fashionable rather than because it
fits is a real failure mode.

The mechanism:

1. The three knowledge base files are split into paragraph chunks, each tagged
   with the heading above it. Paragraph-level chunking suits a knowledge base
   written as short self-contained answers — a fixed token window would cut
   the cancellation policy in half.
2. Chunks are embedded and cached to disk, keyed by a hash of the knowledge
   base so the cache rebuilds itself when a file changes.
3. Queries are compared by cosine similarity.
4. Anything below the similarity floor is discarded. **If nothing survives,
   the assistant says it does not have that information** rather than
   inventing a cancellation policy.

Three backends are tried in order — sentence-transformers, a hybrid TF-IDF,
then plain keyword overlap — so a missing package degrades retrieval quality
instead of taking the app down. `python -m src.rag` prints which one is active
and why the better ones were skipped.

The similarity floor differs per backend, because embedding cosines and TF-IDF
cosines sit on completely different scales. The values were measured against
this knowledge base, not guessed.

---

## 13. Testing

```bash
python run_all_tests.py
```

**1005 tests across ten suites**, none of which need an API key or a network
connection — Groq calls are exercised through an injected stub client, and the
Gradio layer through a stub module.

| Suite | Tests | Covers |
|---|---|---|
| Stage 3 | 95 | validation, storage, atomic writes |
| Stage 4 | 97 | hazard detection, including 22 false-positive cases |
| Stage 5 | 146 | slot hardening, JSON recovery, model fallback |
| Stage 6 | 118 | classification, including the brief's examples verbatim |
| Stage 7 | 101 | scoring arithmetic, hand-checkable |
| Stage 8 | 93 | UI logic, HTML escaping, app structure |
| Stage 9 | 104 | the conversation pipeline |
| Stage 10 | 82 | booking, validation feedback, status changes |
| Stage 11 | 91 | retrieval, and refusing to answer |
| Stage 12 | 78 | analytics |

Suites that write to `requests.csv` back it up first and restore it in a
`finally` block, so they are safe to run during a demo.

Some bugs these tests caught, which is the point of listing them:

- A policy phrase inside a hazard message (*"there is a gas smell, what are
  your hours"*) overwrote the emergency guidance with a knowledge base answer.
- A 4-character request ID collides with ~85% probability across 500 IDs.
- `"Carpet cleaning"` and `"Carpenter"` share five letters, so a prefix-matching
  shortcut routed sofa cleaning to a carpenter.
- A silent `except: continue` in the retrieval backend chain hid a crash and
  quietly downgraded the app to its worst retrieval mode.

---

## 14. Known limitations

- Provider data is fictional and nobody is contacted.
- Storage is CSV, which is fine for one user and not for concurrent ones.
- The conversation only remembers the last few turns.
- Area matching uses six fixed cities, not real geography.
- Retrieval quality depends on which backend is available.
- Emergency helpline numbers in `config.py` should be verified for your region
  before showing this to anyone.

---

## 15. Future improvements

Migrate storage to SQLite or Postgres · real-time provider availability ·
SMS and email confirmation · Urdu and Roman Urdu support · geolocation instead
of a city dropdown · a provider-side portal for accepting jobs · payment
integration · customer reviews feeding back into the rating · a vector store
once the knowledge base outgrows in-memory search · a fine-tuned classifier to
replace the model call · durable conversation memory across sessions.

---

## Team

| Member | Responsibility |
|---|---|
| A | Dataset design and the storage layer |
| B | Prompting, extraction and the safety guard |
| C | Interface and provider cards |
| D | Knowledge base, analytics and documentation |

---

*HomeFix AI is an academic project. It is not a certified technician, it does
not provide repair instructions for gas, electrical or structural work, and in
an emergency you should contact your local emergency services rather than
relying on this app.*
