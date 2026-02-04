# 🏛️ The Colosseum: Agentic AI Recruitment Arbiter

**The Colosseum** is a locally-hosted, privacy-first AI recruitment system that turns a folder of raw PDFs into a ranked list of the Top 10 candidates.

Unlike standard ATS tools that rely on keyword matching, The Colosseum uses a **Tournament Architecture** with an LLM (Llama 3.3 70B) to perform head-to-head battles between candidates, ensuring that only the strongest survive.

---

## ⚡ Key Features

* **🛡️ Privacy First:** All PII (Emails, Phones) is redacted locally *before* ever touching an AI API.
* **⚔️ Colosseum Architecture:** Candidates are not just "scored"; they fight for rank. A **Binary Insertion Sort** algorithm places candidates in their exact competitive position.
* **🧠 "Lazy" Intelligence (JIT):** We use **Just-In-Time (JIT) Scraping**. The system only scrapes a candidate's portfolio/GitHub links *if* they survive the initial "Gatekeeper" battle, saving massive amounts of time and API costs.
* **🧟 Zombie Filter:** Automatically detects and quarantines "Zombie PDFs" (image-only scans) and corrupt files.
* **🕸️ Persistent Memory:** Scraped evidence is cached. If you re-run the tournament, the system remembers the evidence it found last time.

---

## 🛠️ Installation

### 1. Prerequisites

* Python 3.10+
* An [Gemini API Key](https://aistudio.google.com/).

### 2. Setup

Clone the repository and install dependencies:

```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install requirements
pip install -r requirements.txt
```

### 3. Folder Structure

Ensure your project looks like this:

```text
/project_root
├── main.py                 # The Command Center
├── requirements.txt        # Dependencies
├── src/                    # The Logic Core
│   ├── __init__.py
│   ├── extractor.py
│   ├── scout.py
│   └── arbiter.py
└── data/                   # The Data Warehouse
    ├── resumes/            # PUT YOUR PDF RESUMES HERE
    ├── prompts/            # (Auto-generated or manual text files)
    └── job_data/
        └── battle_sheet.json  # Your Criteria

```

---

## 🚀 How to Use

The system is controlled via a unified CLI.

**1. Prepare your Data:**

* Drop your candidate PDFs into `data/resumes/`.
* Edit `data/job_data/battle_sheet.json` to define your hiring criteria (see Configuration below).

**2. Run the General:**

```bash
python main.py

```

**3. Choose Your Mission:**

* **Option 1 (Full Pipeline):** Runs the entire process from PDF to Final Report.
* **Option 4 (Arbiter Only):** Useful if you want to re-rank the existing Top 50 candidates without re-processing PDFs.

**4. View Results:**

* **Top 10 Report:** `data/result/FINAL_REPORT.csv`
* **Full Data:** `data/result/candidates_final.parquet`

---

## 🧠 System Architecture & Logic

Why is the system built this way? Here is the logic behind the three phases.

### Phase 1: The Smart Extractor (`src/extractor.py`)

* **Logic:** **Content Hashing.**
* *Problem:* Candidates often submit the same resume twice with different filenames (`resume_v1.pdf`, `resume_final.pdf`).
* *Solution:* We generate an MD5 hash of the *file content*. If the hash exists, we skip it. This prevents "Split Brain" (ranking the same person twice).


* **Logic:** **Markdown Conversion.**
* We convert PDFs to **Markdown** (not plain text). This preserves headers and tables, helping the AI understand that "Python" listed under "Skills" is different from "Python" listed under "Hobby".



### Phase 2: The Scout (`src/scout.py`)

* **Logic:** **The 500  50 Filter.**
* Running a 70B parameter LLM on 500 candidates is too expensive and slow.
* *Solution:* We use **Vector Search** (Cosine Similarity) with a lightweight local model (`all-MiniLM-L6-v2`) to instantly find the Top 50 semantic matches.


* **Logic:** **The Privacy Shield.**
* Before sending data to the Arbiter (Cloud API), the Scout uses Regex + Neural Entity Recognition to redact Emails and Phone Numbers.



### Phase 3: The Arbiter (`src/arbiter.py`)

This is the core innovation. It uses a **Colosseum Tournament** structure.

1. **The Arena:** A fixed list of size 10. Sorted from Rank #1 (God Tier) to Rank #10 (Gatekeeper).
2. **The Challenger:** A new candidate enters the arena.
3. **The Gatekeeper Battle:**
* The Challenger fights the *weakest* person in the Arena (#10).
* *Why?* If they can't beat #10, they are rejected immediately. We don't waste time comparing them to #1.


4. **JIT (Just-In-Time) Fact Checking:**
* We **do not scrape links** for all 50 candidates.
* The scraper triggers *only* when a candidate enters a battle.
* *Benefit:* We save ~80% of scraping time/risk by ignoring the "trash" candidates who never make it to the Arena.


5. **Binary Insertion Sort:**
* If a Challenger beats #10, they are in. But where?
* Instead of fighting #9, then #8, then #7 (slow), we use **Binary Search**.
* The Challenger fights the **Middle** (#5). If they win, they fight #2. If they lose, they fight #7.
* *Benefit:* Finds the exact rank in ~3 API calls instead of 10.



---
You are absolutely right. I missed listing the **most important prompt**—the one that extracts the candidate's Name and Experience while they fight their first battle.

Without this, your final report would have blank columns for `Name` and `YOE`.

Here is the missing file and the updated README section.

### **1. The Missing File: `data/prompts/judge_newcomer.txt**`

Create this file. This is the "Dual-Task" prompt: it judges the winner **AND** extracts metadata (Name, YOE, Role) simultaneously to save tokens.

```text
You are the Arbiter.
Your goal is to compare two candidates AND extract their missing metadata.

=== THE BATTLE SHEET (CRITERIA) ===
Role: {{role}}
Must Haves: {{must_haves}}
Deal Breakers: {{deal_breakers}}

=== CANDIDATE A (Challenger) ===
ID: {{id_a}}
Resume & Evidence:
{{text_a}}

=== CANDIDATE B (Opponent) ===
ID: {{id_b}}
Resume & Evidence:
{{text_b}}

=== INSTRUCTIONS ===
1. Analyze both dossiers.
2. EXTRACT the following for BOTH candidates (Infer from text if not explicit):
   - "name": Full Name (e.g. "Jane Doe")
   - "yoe": Years of Experience (Numeric integer, e.g. 5)
   - "current_role": Most recent job title.
3. DECIDE: Who is the stronger candidate for this specific role?
4. REASON: Why did they win? (Be specific: "A has deployed to AWS, B has not").

=== OUTPUT FORMAT (STRICT JSON) ===
{
    "candidate_a_details": {
        "name": "Extracted Name",
        "yoe": 5,
        "current_role": "Title"
    },
    "candidate_b_details": {
        "name": "Extracted Name",
        "yoe": 3,
        "current_role": "Title"
    },
    "winner_id": "{{id_a}}",
    "reason": "One sentence explaining the victory."
}

```

---

## ⚙️ Configuration

### The Prompts

You can tweak the AI's personality by editing the text files in `data/prompts/`. The system uses a **3-Tier Prompt Strategy** to optimize for cost and accuracy:

* **`judge_newcomer.txt` (The Investigator):**
* *Trigger:* Used in a candidate's very first battle.
* *Goal:* Compares candidates **AND** extracts their Name, Years of Experience, and Current Role. This ensures we don't pay for a separate extraction API call.


* **`judge_gatekeeper.txt` (The Bouncer):**
* *Trigger:* Used when the Arena is full (10/10).
* *Goal:* A fast, ruthless "Yes/No" check. If the Challenger has a deal-breaker (e.g., dead link), they are rejected immediately.


* **`judge_ranker.txt` (The Judge):**
* *Trigger:* Used during the Binary Search inside the Top 10.
* *Goal:* A deep, nuanced comparison to determine exact ranking (e.g., Rank #4 vs Rank #5).



---

### **3. Code Verification (Logic Check)**

Just to confirm, your `src/arbiter.py` **already has the logic** to handle this. Look at `_battle()`:

```python
        # 5. Extraction Logic (Only for 'newcomer')
        if mode == "newcomer":
            # Save extracted metadata to DF
            for key in ['candidate_a_details', 'candidate_b_details']:
                # ... (Logic to save Name/YOE to dataframe) ...

```
