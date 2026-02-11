import sys
import os
import json
import pandas as pd
import re
from pathlib import Path
from rich.progress import track
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine import Engine
from src.masquerade import Masquerade

# --- CONFIG ---
DATA_DIR = Path("data")
RESULT_DIR = DATA_DIR / "result"
JOB_DATA_DIR = DATA_DIR / "job_data"
BATTLE_SHEET_PATH = JOB_DATA_DIR / "battle_sheet.json"

PROCESSED_FILE = RESULT_DIR / "candidates_processed.parquet" 
OUTPUT_JSON = RESULT_DIR / "enriched_report.json"          

console = Console()

class Auditor:
    def __init__(self, MAX_TOURNAMENT_SIZE=10, RESUME_LEN=3000):
        self.engine = Engine()
        self.len = RESUME_LEN
        self.no_of_candidates = MAX_TOURNAMENT_SIZE
        self.target_skills = self._load_skills_from_sheet()

    def _load_skills_from_sheet(self):
        if not BATTLE_SHEET_PATH.exists(): return []
        try:
            with open(BATTLE_SHEET_PATH, 'r') as f:
                data = json.load(f)
                if isinstance(data, list): data = data[0]
                return data.get("keywords_for_scan", [])
        except: return []

    # --- PHASE 2 WORKER (Narrative) ---
    def _worker_phase_2(self, cand):
        """
        Combines Phase 1 Metadata (Facts) with Phase 6 Battle Logs (Verdict).
        Since Colosseum has already filtered 'High Risk' candidates, 
        we focus purely on Data Enrichment (Notice Period, Current Company, etc.).
        """
        # --- HELPER: SERIALIZATION SANITIZER ---
        def clean_data(val):
            """Converts NumPy arrays/NaNs to standard Python types."""
            if val is None: return None
            if hasattr(val, "tolist"): return val.tolist()  # Fixes ndarray error
            if pd.isna(val): return None
            return val
        # ---------------------------------------
        # 1. Unpack Phase 1 Metadata (The "Truth" extracted earlier)
        # This contains the rich data like Notice Period, Company, etc.
        meta = json.loads(cand.get('metadata', '{}'))
        
        real_name = meta.get('full_name') or f"Candidate_{cand['id']}"
        contact = meta.get('contact', {})  # Nested dict from Phase 1
        risk_audit = meta.get('risk_audit', {})
        notice_data = meta.get('notice_period', {})
        
        # 2. Extract Business Logic Fields (The "Money" Data)
        curr_company = meta.get('current_company', 'N/A')
        notice_days = notice_data.get('days', 'N/A')
        notice_status = notice_data.get('status', 'Unknown')
        
        # 3. Clean Contact Info (Prioritize Phase 1 Extraction)
        email = clean_data(cand.get('emails')) or contact.get('email') or 'N/A'
        phone = clean_data(cand.get('phones')) or contact.get('phone') or 'N/A'
        links = clean_data(cand.get('links')) or contact.get('links') or []
        location = contact.get('location', meta.get('location', 'N/A'))

        # 4. Generate "Victory Verdict" (Anti-Hallucination Mode)
        raw_log = " | ".join(cand.get('battle_log', []))
        rank = cand.get('Rank', 'N/A')
        
        prompt = f"""
        ### ROLE: Lead Recruiter & Auditor
        ### TASK: Write a final selection justification for: {real_name} (Rank #{rank}).
        
        ### INPUT DATA:
        1. RESUME EXTRACT: "{cand.get('safe_text', '')[:self.len]}..."
        2. COMPARISON LOGS: {raw_log}
        
        ### STYLISTIC GUIDELINES:
        - Tone: Clinical, Objective, and Executive-Level.
        - Format: A single, dense paragraph.
        - Forbidden: Do not use words like "battle", "fight", "defeated", "lost", "challenger", or "opponent". Use "selected because", "outperformed others", or "surpassed others" (not directly pointing to opponent or mentioning any opponent id e.g.: c5d6f7).
        
        ### CRITICAL INTEGRITY RULES (NON-NEGOTIABLE):
        1. ZERO HALLUCINATION POLICY: You may ONLY mention skills/companies explicitly visible in the 'RESUME EXTRACT'. If it's not in the text, it doesn't exist.
        2. NO FLUFF: Do not use empty phrases like "visionary leader" or "unparalleled synergy" unless proven by data.
        3. EVIDENCE-BASED: When you claim they are better, cite the specific years of experience, skillset, tools, knowledge, or company name that proves it from resume.
        4. HANDLING WEAK DATA: If the resume is short, malformed, or vague, do NOT invent virtues. Instead, write: "Candidate selected based on available metadata, though resume detail is limited."
        
        ### OUTPUT STRING ONLY:
        Start immediately with: 
        "{real_name} was selected because..."
        """

        narrative = self.engine.think(prompt)
        if isinstance(narrative, dict): narrative = str(list(narrative.values())[0])
        narrative_text = str(narrative).strip('"\' {}[]')

        # 5. Return the Unified Record (Enriched with Phase 1 Data)
        return {
            'Rank': rank,
            'file_name': meta.get('file_name', 'N/A'),
            'Name': real_name,
            'Match Score': cand.get('rerank_score', 0),
            
            # Risk & Audit (Passthrough from Phase 1)
            'Risk Level': risk_audit.get('level', 'Low'),
            'Reason': f"{risk_audit.get('flag', '')}: {risk_audit.get('reason', 'No specific flags.')}".strip(': '),

            # Vitals
            'Location': location,
            'Years Exp': meta.get('yoe', 'N/A'),
            'Email': email,
            'Phone': phone,
            'Links': links,
            
            # --- NEW: CRITICAL BUSINESS DATA ---
            'Current Company': curr_company,
            'Notice Period': f"{notice_days} Days ({notice_status})",
            # -----------------------------------
            
            # Content
            'Professional Summary': meta.get('summary', ''),
            'Battle Narrative': narrative_text,
            'Key Skills': cand.get('regex_skills', '')
        }

    def generate_report(self):
        """Phase 2: Adaptive Narrative Generation."""
        if not PROCESSED_FILE.exists(): return
        
        df = pd.read_parquet(PROCESSED_FILE)
        if 'Rank' not in df.columns: df['Rank'] = range(1, len(df) + 1)
        candidates = df.sort_values('Rank').to_dict(orient='records')

        console.print("[yellow]🔍 Probing Engine for Narrative Phase...[/yellow]")
        final_enriched = [self._worker_phase_2(candidates[0])]

        remaining = candidates[1:]
        if not remaining:
            return self._save_final_reports(final_enriched)

        is_cloud = self.engine.is_cloud_alive
        workers = 5 if is_cloud else 1
        msg = "[bold green]🚀 Swarming (n=5)[/bold green]" if is_cloud else "[bold red]⚠️ Sequential (n=1)[/bold red]"
        console.print(f"{msg}")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            processed = list(track(executor.map(self._worker_phase_2, remaining), 
                                  total=len(remaining), 
                                  description="Generating Narratives..."))
            final_enriched.extend(processed)

        self._save_final_reports(final_enriched)

    def _save_final_reports(self, data):
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        console.print(f"[green]✅ Reports Saved to JSON.[/green]")