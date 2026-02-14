import json
import sys
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
from src.masquerade import Masquerade
from src.colosseum import Colosseum
from src.auditor import Auditor
from src.datapack import DataPackGenerator
from src.designer import generate_design_pdf

# --- CONFIGURATION ---
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "resumes"
QUARANTINE_DIR = DATA_DIR / "quarantine"
RESULT_DIR = DATA_DIR / "result"
SHEET_PATH = DATA_DIR / "job_data" / "battle_sheet.json"

# 🔒 SAFETY VALVE: Colosseum will NEVER fight more than this many people.
MAX_TOURNAMENT_SIZE = 50
WINNERS_CIRCLE = 10
TAKE_RISK = False
PRIVACY_MODE = False
RESUME_LEN = 3000 # 3000 for jr/mid level roles and 5000 for senior ones

# Ensure directories exist
for d in [DATA_DIR, RAW_DIR, RESULT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

console = Console()

class AgencyControl:
    def __init__(self):
        self.data_dir = DATA_DIR
        self.raw_dir = RAW_DIR
        self.quarantine_dir = QUARANTINE_DIR
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

    def run_oracle(self):
        console.print(Panel("[bold green]Phase 2: Oracle Rescue[/bold green]", border_style="green"))
        # Run Oracle Rescue immediately after extraction
        run_oracle_rescue()

    def run_scout(self):
        console.print(Panel("[bold magenta]Phase 3: The Scout[/bold magenta]", border_style="magenta"))
        
        input_path = self.result_dir / "candidates.parquet"
        if not input_path.exists():
            console.print("[red]❌ No candidates found. Run Extractor first.[/red]")
            return

        if not self.sheet_path.exists():
            console.print(f"[bold red]❌ Battle Sheet missing at {self.sheet_path}[/bold red]")
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

        with open(self.sheet_path, 'r') as f:
            sheet = json.load(f)
            
            # --- THE FIX: USE THE VECTOR SUMMARY ---
            # If the summary exists, use it. Otherwise, fall back to Role + Skills.
            criteria_text = sheet.get('summary_for_vector_search', f"{sheet['role']} {sheet['must_haves']}")

            console.print(f"[cyan]🧠 Scout aiming for: {criteria_text[:100]}...[/cyan]")

            anchors = sheet.get('keywords_for_scan', [])
            if anchors:
                console.print(f"[bold yellow]⚓ Anchors deployed:[/bold yellow] {', '.join(anchors)}")

        scout = SmartScout()
        output_path = self.result_dir / "candidates_scouted.parquet"
        
        scout.filter_candidates(
            parquet_file=input_path,
            battle_sheet_text=criteria_text,
            output_file=output_path,
            top_k=scout_k,
            anchors=anchors
        )

    def run_reranker(self):
        console.print(Panel("[bold yellow]Phase 4: The Re-Ranker (Precision Filter)[/bold yellow]", border_style="yellow"))

        input_path = self.result_dir / "candidates_scouted.parquet"
        if not input_path.exists():
            console.print("[red]❌ No candidates found. Run Extractor first.[/red]")
            return
            
        # 2. RE-RANKER FORMULA: The "Arbiter Protection" Cap
        # The Re-Ranker must reduce the pool to the MAX_TOURNAMENT_SIZE (20).
        df = pd.read_parquet(input_path)
        scouted_count = len(df)
        
        # Takes the smaller of: (10% of candidates) OR (Max Tournament Size)
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

    def run_masquerade(self):
        # --- ANTI BIAS BLOCK ---
        reranked_file = self.result_dir / "candidates_reranked.parquet"
        df = pd.read_parquet(reranked_file)
        console.print(Panel("[bold yellow]Phase 5: 🎭 Masquerade Protocol (Blind Hiring)[/bold yellow]", border_style="yellow"))
        masquerade = Masquerade(df, RESUME_LEN, PRIVACY_MODE)
        masquerade.mask_candidates() 
               
    def run_colosseum(self):
        console.print(Panel("[bold red]Phase 6: The Colosseum (LLM Tournament)[/bold red]", border_style="red"))
        
        reranked_file = self.result_dir / "candidates_reranked.parquet"
        if not reranked_file.exists():
            console.print("[bold red]❌ Run Re-Ranker (Option 3) first![/bold red]")
            return
        
        df = pd.read_parquet(reranked_file)
        console.print(f"⚔️  The Colosseum is Open. {len(df)} candidates entering...")

        with open(self.sheet_path, 'r') as f: sheet = json.load(f)
        console.print(f"[bold green]📋 Battle Criteria: {sheet['role']}[/bold green]")

        colosseum = Colosseum(df, sheet, RESUME_LEN)
        top_ids = colosseum.run_tournament(winners_circle=WINNERS_CIRCLE, take_risk=TAKE_RISK) 
        
        if not top_ids: return

        # Generate Report
        final_df = colosseum.df[colosseum.df['id'].isin(top_ids)].copy()
        final_df['rank'] = final_df['id'].apply(lambda x: top_ids.index(x) + 1)
        final_df = final_df.sort_values('rank')
        
        report_cols = ['rank', 'meta_name', 'meta_role', 'battle_log', 'evidence', 'id', 'safe_text', 'contact_info']
        cols_to_keep = [c for c in report_cols if c in final_df.columns]
        
        final_df[cols_to_keep].to_json(self.result_dir / "final_report.json", orient='records', indent=2)
        console.print(Panel(f"🏆 [bold]Tournament Complete! Report Generated.[/bold]", border_style="green"))

    def run_auditor(self):
        console.print(Panel("[bold purple]Phase 7: Auditor (Deep Analysis)[/bold purple]", border_style="purple"))
        Auditor(MAX_TOURNAMENT_SIZE, RESUME_LEN).generate_report()

    def export_lite_results(self):
        """Phase 8: Generating Professional Data Pack (CSV)."""
        console.print(Panel("[bold blue]Phase 8: Generating Master Executive Data Pack[/bold blue]", border_style="blue"))
        # Call the new robust module
        generator = DataPackGenerator(self.result_dir)
        generator.generate()

    def run_designer(self):
        console.print(Panel("[bold green]Phase 9: Designer (PDF Dossier)[/bold green]", border_style="green"))
        generate_design_pdf()

    def reset_system(self):
        """Option 9: Factory Reset"""
        console.print(Panel("[bold red]⚠️  WARNING: FACTORY RESET INITIATED[/bold red]", border_style="red"))
        console.print("This will PERMANENTLY DELETE all files in:")
        console.print(f"1. {self.raw_dir} (Resumes)")
        console.print(f"2. {self.quarantine_dir} (Quarantine)")
        console.print(f"3. {self.result_dir} (Reports & Databases)")
        
        confirm = input("\nType 'RESET' to confirm deletion: ").strip()
        
        if confirm != "RESET":
            console.print("[yellow]🚫 Reset cancelled. Data is safe.[/yellow]")
            return

        # List of folders to purge
        folders_to_purge = [self.raw_dir, self.quarantine_dir, self.result_dir] # self.raw_dir, self.quarantine_dir, 
        
        for folder in folders_to_purge:
            if folder.exists():
                count = 0
                for file in folder.iterdir():
                    if file.is_file():
                        try:
                            file.unlink()
                            count += 1
                        except Exception as e:
                            console.print(f"[red]Failed to delete {file.name}: {e}[/red]")
                console.print(f"   🗑️  Deleted {count} files from [bold]{folder.name}[/bold]")
        
        console.print("\n[bold green]✅ System Reset Complete. All data wiped.[/bold green]")
        console.print("[dim]Exiting application...[/dim]")
        sys.exit(0)

    def menu(self):
        while True:
            console.print(Panel.fit(
                "1. Extractor (PDF -> Text)\n"
                "2. Oracle (IMG -> Text)\n"
                "3. Scout (Noice Filter)\n"
                "4. Re-Ranker (Top Filter)\n"
                "5. Masquerade (Blind Hiring)\n"
                "6. Colosseum (Tournament)\n"
                "7. Auditor (Deep Analysis)\n"   
                "---------------------------\n"  
                "8. Export Lite Report (Fast CSV)\n"
                "9. Generate Design PDF\n"
                "---------------------------\n"
                "r. [bold red]RESET SYSTEM (Delete & Quit)[/bold red]\n"
                "q. [bold yellow]Quit[/bold yellow]",
                title="Control Tower",
                border_style="bold blue"
            ))
            
            choice = input("Option: ").strip().lower()
            
            if "1" in choice: self.run_extractor()
            if "2" in choice: self.run_oracle()
            if "3" in choice: self.run_scout()
            if "4" in choice: self.run_reranker()
            if "5" in choice: self.run_masquerade()
            if "6" in choice: self.run_colosseum()
            if "7" in choice: self.run_auditor()
            if "8" in choice: self.export_lite_results()
            if "9" in choice: self.run_designer()
            elif "r" in choice: self.reset_system()
            if "q" in choice: break

if __name__ == "__main__":
    app = AgencyControl()
    app.menu()