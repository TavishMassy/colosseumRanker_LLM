import sys
import os
import json
import pandas as pd
import re
from pathlib import Path
from rich.progress import track
from rich.console import Console
from rich.panel import Panel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine import Engine

# --- CONFIG ---
DATA_DIR = Path("data")
RESULT_DIR = DATA_DIR / "result"
JOB_DATA_DIR = DATA_DIR / "job_data"
BATTLE_SHEET_PATH = JOB_DATA_DIR / "battle_sheet.json"

INPUT_FILE = RESULT_DIR / "candidates_processed.parquet" 
OUTPUT_CSV = RESULT_DIR / "Agency_Client_Report.csv"       
OUTPUT_JSON = RESULT_DIR / "enriched_report.json"          

console = Console()

class Auditor:
    def __init__(self, MAX_TOURNAMENT_SIZE=10):
        self.engine = Engine()
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

    def _scan_skills(self, text):
        if not isinstance(text, str) or not self.target_skills: return ""
        found = {s for s in self.target_skills if re.search(r'\b' + re.escape(s.lower()) + r'\b', text.lower())}
        return ", ".join(list(found))

    def generate_report(self):
        if not INPUT_FILE.exists(): 
            console.print("[red]❌ Input file not found. Run the tournament first.[/red]")
            return

        df = pd.read_parquet(INPUT_FILE)
        if 'rank' not in df.columns: df['rank'] = range(1, len(df) + 1)
        
        # Take top N candidates
        top_candidates = df.sort_values('rank').head(self.no_of_candidates).to_dict(orient='records')
        
        # Mapping for Pass 2: { "id": "Name" }
        id_to_name_map = {}
        processed_data = []

        # --- PASS 1: EXTRACTION (Metadata) ---
        console.print(Panel(f"[bold cyan]Pass 1/2: Extracting Metadata (Top {len(top_candidates)})[/bold cyan]"))
        
        for cand in track(top_candidates, description="Analyzing Resumes..."):
            resume_text = cand.get('safe_text', '')[:3000]
            
            # UPDATED PROMPT: Now asks for Location
            prompt = f"""
            EXTRACT JSON FROM RESUME:
            1. "full_name": Name
            2. "location": City, Country (or "Remote" if stated)
            3. "yoe": Years of Experience (int)
            4. "risk": "High" if frequent job changes respective of fiel, else "Low"
            5. "risk_reason": 5 words explaining the risk (e.g. "Frequent short tenures")
            6. "summary": 20-word professional bio.

            RESUME: {resume_text}
            """
            
            intel = self.engine.think(prompt)

            # Fallback logic for Name
            name = intel.get('full_name') or cand.get('meta_name') or f"Candidate {cand['id'][:4]}"
            if name in id_to_name_map.values():
                name = f"{name} ({cand['id'][:4]})"
            
            id_to_name_map[cand['id']] = name
            cand['extracted'] = intel
            cand['regex_skills'] = self._scan_skills(resume_text)
            processed_data.append(cand)

        # --- PASS 2: NARRATIVE SUMMARY (Battle Log Translation) ---
        console.print(Panel(f"[bold magenta]Pass 2/2: Summarizing Battle History[/bold magenta]"))
        
        final_enriched = []
        for cand in track(processed_data, description="Summarizing Battles..."):
            raw_log = " | ".join(cand.get('battle_log', []))
            
            prompt = f"""
            Translate this Battle Log into a 1-sentence professional 'Victory Narrative'.
            Replace these IDs with Names: {json.dumps(id_to_name_map)}
            
            CANDIDATE: {id_to_name_map[cand['id']]}
            LOG: {raw_log}
            
            Example: "Defeated John Doe due to superior cloud architecture knowledge."
            RETURN PLAIN TEXT ONLY.
            """
            
            narrative = self.engine.think(prompt)
            # Handle if engine returns dict instead of string
            if isinstance(narrative, dict): 
                narrative = narrative.get('victory_narrative') or narrative.get('summary', str(narrative))

            row = {
                'Rank': cand.get('rank'),
                'Name': id_to_name_map[cand['id']],
                'Location': cand['extracted'].get('location', 'Unknown'),
                'Match Score': cand.get('rerank_score', 0),
                'Years Exp': cand['extracted'].get('yoe', 'N/A'),
                'Risk Level': cand['extracted'].get('risk', 'Low'),
                'Risk Reason': cand['extracted'].get('risk_reason', 'N/A'),                
                'Key Skills': cand['regex_skills'],
                'Professional Summary': cand['extracted'].get('summary', ''),
                'Narrative': narrative,
                'Verified Links': cand.get('evidence', ''),
                'ID': cand['id']
            }
            final_enriched.append(row)

        # --- NEW: INTERNAL SANITIZATION PASS ---
        console.print("[yellow]🧹 Sanitizing AI Narratives...[/yellow]")
        for entry in final_enriched:
            narrative = str(entry.get('Narrative', ''))
            
            # Handle Ollama JSON leaks
            if '{' in narrative or '}' in narrative:
                entry['Narrative'] = narrative.split(':')[-1].replace('}', '').replace('{', '').strip("'\" ")

        # --- SAVE RESULTS ---
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(final_enriched, f, indent=4)
        
        final_df = pd.DataFrame(final_enriched)
        final_df.to_csv(OUTPUT_CSV, index=False)
        console.print(Panel(f"🏆 Heavy Report Ready!\n📂 CSV: {OUTPUT_CSV}\n📂 JSON: {OUTPUT_JSON}", border_style="green"))

if __name__ == "__main__":
    Auditor().generate_report()