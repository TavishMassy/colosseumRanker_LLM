# 🏛️ The Colosseum Protocol

### *Autonomous Recruitment Audit & Ranking Architecture*

**The Colosseum** is an enterprise-grade AI pipeline designed to automate the recruitment "due diligence" process. Unlike standard resume parsers, Colosseum acts as a **Brutal Executive Auditor**: it strips away buzzwords, validates claims against live web evidence, anonymizes PII to remove bias, and ranks candidates using a rigorous "Tournament" system before generating executive-level dossiers.

It operates on a **Hybrid Engine**, capable of switching seamlessly between Cloud (Gemini) for speed and Local (Llama-3/Ollama) for privacy/GDPR compliance.

---

## ⚡ Core Capabilities

### 1. 🛡️ The "Euro-Local" Hybrid Engine

* **Smart Switching:** Detects API keys to determine whether to use Cloud (Gemini) or Local (Llama-3) backends.
* **Sandwich Context Strategy:** For local models with limited context (e.g., 4k tokens), it uses a "Sliding Window" technique to process massive resumes without forgetting instructions or output formats.
* **Vision Rescue:** An "Oracle" module uses Vision LLMs to OCR and rescue image-based resumes from the quarantine folder.

### 2. 🕵️ Deep-Dive Intelligence (The Masquerade)

* **PII Anonymization:** Using a Split-Protocol, it extracts and masks Name, Phone, and Email (e.g., `CANDIDATE_4a2b`) *before* business logic is applied, ensuring unbiased analysis.
* **Live Forensic Scraping:** The `FactChecker` module uses **Playwright** to visit candidate links (GitHub, Portfolios) and scrape "Ground Truth" evidence to verify resume claims against reality.
* **Risk Audit:** Classifies candidates as **High/Medium/Low Risk** based on job hopping, notice period discrepancies, and timeline gaps.

### 3. ⚔️ The Arena (Ranking & Tournament)

* **Cross-Encoder Re-Ranking:** Uses MS-MARCO models to score candidates not just on keywords, but on semantic relevance to the "Battle Sheet".
* **Binary Search Tournament:** Candidates fight 1v1 "battles" using LLM logic to find their exact insertion point in the ranking list, rather than arbitrary scoring.
* **Deal-Breaker Sniper:** Automatically penalizes candidates missing mandatory certifications or specific "Must-Haves" (e.g., Notice Period > 60 Days).

### 4. 🧪 Synthetic Stress Testing

* **Chaos Generator:** Includes a `resume_gen.py` module that generates adversarial synthetic resumes ("Job Hoppers", "Corporate Traps" with 90-day notice periods, "Ghosts" with missing contact info) to validate the system's detection logic.

---

## 🛠️ Installation

### Prerequisites

* Python 3.10+
* [Ollama](https://ollama.com/) (For Local Mode)
* [Playwright](https://playwright.dev/) (For Web Scraping)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/colosseum.git
cd colosseum

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Install Playwright Browsers (Required for 'Masquerade' Scraper)
playwright install chromium

# 4. (Optional) Pull Local Model for Privacy Mode
ollama pull llama3

```

---

## ⚙️ Configuration

### 1. The Battle Sheet

Define your target role in `data/job_data/battle_sheet.json`. This controls the AI's judgment criteria.

```json
{
  "role": "Senior Backend Engineer",
  "must_haves": ["Rust", "Kubernetes", "English C1"],
  "deal_breakers": ["No remote experience", "Notice period > 60 days"],
  "cultural_vibe": "Fast-paced, chaotic, ownership-heavy",
  "keywords_for_scan": ["Kafka", "Redis", "System Design"]
}

```

### 2. Environment

Create a `.env` file (Optional). If skipped, the system defaults to **Local Mode**.

```ini
GEMINI_API_KEY=AIzaSy... 

```

---

## 🚀 Execution Workflow

The system is controlled via the **Agency Control Tower** (`main.py`).

```bash
python main.py

```

This launches an interactive CLI menu to guide you through the 9-Phase Pipeline:

### 📥 Phase 1: Ingestion

* **Option 1 (Extractor):** Hashes and extracts text from PDFs/DOCX. Deduplicates by content MD5.
* **Option 2 (Oracle):** Rescues corrupt or image-based PDFs using Vision LLMs.

### 🧠 Phase 2: Intelligence

* **Option 3 (Scout):** Vector-based filtering (MiniLM) to reduce the pool size.
* **Option 4 (Re-Ranker):** Semantic Cross-Encoder scoring to bubble up the best matches.
* **Option 5 (Masquerade):** The heavy lifting. Masks PII, scrapes web evidence, and performs the initial Risk Audit.

### ⚔️ Phase 3: The Tournament

* **Option 6 (Colosseum):** Candidates fight for rank using Binary Search battles. High-risk candidates are purged.
* **Option 7 (Auditor):** Writes the final "Investment Memo" for the winners.

### 📤 Phase 4: Publication

* **Option 8 (Lite Export):** Generates a CSV Data Pack.
* **Option 9 (Designer):** Generates the final PDF Dossier.

---

## 🛠️ Developer Utilities

The project includes root-level tools for testing and debugging:

### `resume_gen.py` (Chaos Monkey)

Generates synthetic resumes to stress-test the Auditor's risk detection.

```bash
python resume_gen.py

```

* **Creates:** "Alphas" (Perfect candidates), "Traps" (Good skills, 90-day notice), "Hoppers" (Job hoppers), and "Ghosts" (No contact info).

### `peek_data.py` (Data Inspector)

Allows you to inspect the binary Parquet databases directly in the terminal without needing a data viewer.

```bash
python peek_data.py

```

* **Displays:** The first 5 rows of `candidates_reranked.parquet` with rich formatting.

---

## 📂 Project Structure

```text
colosseum/
├── main.py               # 🎛️ The Control Tower (CLI Entry Point)
├── resume_gen.py         # 🧪 Synthetic Data Generator
├── peek_data.py          # 🧐 Parquet Data Inspector
├── requirements.txt      # 📦 Dependency List
├── data/
│   ├── resumes/          # Raw Input
│   ├── quarantine/       # Corrupt/Image files (Rescued by Oracle)
│   └── result/           # Parquet DBs, JSON Reports, Final PDFs
└── src/
    ├── engine.py         # Cloud Engine (Gemini)
    ├── backup_engine.py  # Local Engine (Llama-3 Sandwich Logic)
    ├── extractor.py      # Hash-based Ingestion & OCR
    ├── oracle.py         # Vision LLM Rescue for images
    ├── scout.py          # Vector Search & Density Audit
    ├── reranker.py       # Cross-Encoder & Deal-Breaker Logic
    ├── masquerade.py     # PII Masking, Web Scraping, Risk Audit
    ├── auditor.py        # Narrative Generation
    ├── designer.py       # PDF Generator
    └── datapack.py       # CSV Generator

```

---

## ⚠️ Security & Privacy

* **GDPR Compliance:** When no API key is provided, the system runs entirely on `localhost` using Ollama. No candidate data leaves the machine.
* **Bias Mitigation:** The **Masquerade** module uses a strict "Split Protocol":
1. **Op A (PII Scout):** Extracts & Masks Identity.
2. **Op B (Analyst):** Analyzes *only* the masked text for skills/risk.



---

> *"Treats every hire as a high-stakes capital allocation."* — **The Colosseum Protocol**
