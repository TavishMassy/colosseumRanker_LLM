import json
import time
import math
import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# --- IMPORT MODULES ---
from src.extractor import ResumeExtractor
from src.oracle import run_oracle_rescue
from src.scout import SmartScout
from src.reranker import ReRanker
from src.arbiter import Colosseum
from src.forensics import run_forensics as launch_forensics

# --- CONFIGURATION ---
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "resumes"
RESULT_DIR = DATA_DIR / "result"
SHEET_PATH = DATA_DIR / "job_data" / "battle_sheet.json"

# 🔒 SAFETY VALVE: The Arbiter will NEVER fight more than this many people.
# This protects your wallet/CPU even if you input 10,000 resumes.
MAX_TOURNAMENT_SIZE = 20

# Ensure directories exist
for d in [DATA_DIR, RAW_DIR, RESULT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

console = Console()

class AgencyControl:
    def __init__(self):
        self.data_dir = DATA_DIR
        self.raw_dir = RAW_DIR
        self.result_dir = RESULT_DIR
        self.sheet_path = SHEET_PATH

    def run_extractor(self):
        console.print(Panel("[bold cyan]Phase 1: The Extractor[/bold cyan]", border_style="cyan"))
        
        # FIX 1: Initialize without arguments (matches your extractor.py)
        extractor = ResumeExtractor() 
        
        # FIX 2: Define the output path specifically
        output_path = self.result_dir / "candidates.parquet"
        
        # FIX 3: Call the correct method 'run' instead of 'process_all'
        # The 'run' method in your extractor handles the saving internally.
        df = extractor.run(self.raw_dir, output_path)
        
        if df is not None:
            console.print(f"✅ Extracted {len(df)} resumes to {output_path}")
        else:
             console.print("[red]❌ Extraction failed or no resumes found.[/red]")

    def run_rescue(self):
        console.print(Panel("[bold purple]Phase 1.5: Vision Rescue (Oracle)[/bold purple]", border_style="purple"))
        
        # 1. Run the Vision Rescue
        rescued_path = run_oracle_rescue()
        
        # 2. If no files were rescued, we are done
        if not rescued_path or not rescued_path.exists():
            return

        # 3. THE MERGE LOGIC
        main_path = self.result_dir / "candidates.parquet"
        
        if main_path.exists():
            console.print("🔄 Merging rescued candidates into main pool...")
            
            # Load both
            df_main = pd.read_parquet(main_path)
            df_rescue = pd.read_parquet(rescued_path)
            
            # Combine
            df_combined = pd.concat([df_main, df_rescue], ignore_index=True)
            
            # Deduplicate (Safety check by ID)
            df_combined = df_combined.drop_duplicates(subset=['id'])
            
            # Overwrite the main file so Scout sees everyone
            df_combined.to_parquet(main_path, index=False)
            
            console.print(f"✅ Merge Complete. Total Candidates: {len(df_combined)} (+{len(df_rescue)} rescued)")
        else:
            # If main file doesn't exist for some reason, just use the rescued one
            df_rescue.to_parquet(main_path, index=False)
            console.print(f"✅ Main file created from rescued candidates.")

    def run_scout(self):
        console.print(Panel("[bold magenta]Phase 2: The Scout[/bold magenta]", border_style="magenta"))
        
        input_path = self.result_dir / "candidates.parquet"
        if not input_path.exists():
            console.print("[red]❌ No candidates found. Run Extractor first.[/red]")
            return

        # 1. SCOUT FORMULA: 25% Filter
        # The Scout is fast (Vector Math), so it can handle volume.
        # Input: 5000 -> Output: 1250
        df = pd.read_parquet(input_path)
        total_candidates = len(df)
        
        # Keep 25%, but at least 50 (unless total < 50)
        scout_k = math.ceil(total_candidates * 0.25)
        scout_k = max(50, scout_k) 
        scout_k = min(scout_k, total_candidates)
        
        console.print(f"📊 [bold]Funnel Step 1:[/bold] {total_candidates} -> Scout Filter (25%) -> {scout_k}")

        if not self.sheet_path.exists():
            console.print(f"[bold red]❌ Battle Sheet missing at {self.sheet_path}[/bold red]")
            return

        with open(self.sheet_path, 'r') as f:
            sheet = json.load(f)
            criteria_text = f"{sheet['role']} {sheet['must_haves']}"

        scout = SmartScout()
        output_path = self.result_dir / "candidates_scouted.parquet"
        
        scout.filter_candidates(
            parquet_file=input_path,
            battle_sheet_text=criteria_text,
            output_file=output_path,
            top_k=scout_k
        )

    def run_reranker(self):
        console.print(Panel("[bold yellow]Phase 2.5: The Re-Ranker (Precision Filter)[/bold yellow]", border_style="yellow"))
        
        input_path = self.result_dir / "candidates_scouted.parquet"
        if not input_path.exists(): return

        # 2. RE-RANKER FORMULA: The "Arbiter Protection" Cap
        # The Re-Ranker must reduce the pool to the MAX_TOURNAMENT_SIZE (20).
        df = pd.read_parquet(input_path)
        scouted_count = len(df)
        
        # We take the smaller of: (10% of candidates) OR (Max 20)
        # But we ensure we have at least 10 people to fight.
        # Logic: min(20, max(10, 10%))
        
        target_k = min(MAX_TOURNAMENT_SIZE, scouted_count)
        
        console.print(f"📊 [bold]Funnel Step 2:[/bold] {scouted_count} -> Re-Ranker -> Top {target_k}")
        console.print(f"   (Reducing volume to protect Arbiter)")

        if not self.sheet_path.exists(): return

        ranker = ReRanker()
        ranker.rerank(
            input_file=input_path,
            output_file=self.result_dir / "candidates_reranked.parquet",
            battle_sheet_path=self.sheet_path,
            top_k=target_k 
        )

    def run_arbiter(self):
        console.print(Panel("[bold red]Phase 3: The Arbiter (LLM Tournament)[/bold red]", border_style="red"))
        
        reranked_file = self.result_dir / "candidates_reranked.parquet"
        
        if not reranked_file.exists():
            console.print("[bold red]❌ Run Re-Ranker (Option 3) first![/bold red]")
            return
        
        df = pd.read_parquet(reranked_file)
        console.print(f"⚔️  The Colosseum is Open. {len(df)} candidates entering...")

        with open(self.sheet_path, 'r') as f: sheet = json.load(f)
        console.print(f"[bold green]📋 Battle Criteria: {sheet['role']}[/bold green]")

        colosseum = Colosseum(df, sheet)
        top_10_ids = colosseum.run_tournament(test_mode=False) 
        
        if not top_10_ids: return

        # Generate Report
        final_df = colosseum.df[colosseum.df['id'].isin(top_10_ids)].copy()
        final_df['rank'] = final_df['id'].apply(lambda x: top_10_ids.index(x) + 1)
        final_df = final_df.sort_values('rank')
        
        report_cols = ['rank', 'meta_name', 'meta_role', 'battle_log', 'evidence', 'id', 'safe_text', 'contact_info']
        cols_to_keep = [c for c in report_cols if c in final_df.columns]
        
        final_df[cols_to_keep].to_json(self.result_dir / "final_report.json", orient='records', indent=2)
        console.print(Panel(f"🏆 [bold]Tournament Complete! Report Generated.[/bold]", border_style="green"))

    def run_forensics(self):
        console.print(Panel("[bold purple]Phase 5: Forensics (Deep Analysis)[/bold purple]", border_style="purple"))
        launch_forensics()

    def run_full_pipeline(self):
        self.run_extractor()
        time.sleep(1)
        self.run_rescue()     
        time.sleep(1)
        self.run_scout()
        time.sleep(1)
        self.run_reranker()
        time.sleep(1)
        self.run_arbiter()
        time.sleep(1)
        self.run_forensics()

    def menu(self):
        while True:
            console.print(Panel.fit(
                "1. Extractor (PDF -> Text)\n"
                "2. Vision Rescue (Quarantine -> Text)\n"
                "3. Scout (25% Filter)\n"
                "4. Re-Ranker (Top 20)\n"
                "5. Arbiter (Tournament)\n"
                "6. Forensics (Deep Analysis)\n"     
                "7. Run ALL\n"
                "q. Quit",
                title="Control Tower",
                border_style="bold blue"
            ))
            
            choice = input("Option: ").strip().lower()
            
            if choice == "1": self.run_extractor()
            elif choice == "2": self.run_rescue()
            elif choice == "3": self.run_scout()
            elif choice == "4": self.run_reranker()
            elif choice == "5": self.run_arbiter()
            elif choice == "6": self.run_forensics() 
            elif choice == "7": self.run_full_pipeline()
            elif choice == "q": break

if __name__ == "__main__":
    app = AgencyControl()
    app.menu()