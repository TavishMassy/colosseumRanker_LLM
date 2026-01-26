import sys
import os
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Import your modules (Ensure __init__.py exists in src/)
from src.extractor import SmartExtractor
from src.scout import SmartScout
from src.arbiter import Colosseum

console = Console()

class AgencyControl:
    def __init__(self):
        self.root_dir = Path(".")
        self.data_dir = self.root_dir / "data"
        self.resumes_dir = self.data_dir / "resumes"
        self.result_dir = self.data_dir / "result"
        self.job_data_dir = self.data_dir / "job_data"
        
        # Files
        self.candidates_parquet = self.result_dir / "candidates.parquet"
        self.top50_parquet = self.result_dir / "candidates_top50.parquet"
        self.battle_sheet_path = self.job_data_dir / "battle_sheet.json"

    def check_setup(self):
        """Ensures folders exist."""
        for d in [self.resumes_dir, self.result_dir, self.job_data_dir, self.data_dir / "prompts"]:
            d.mkdir(parents=True, exist_ok=True)

    def run_extractor(self):
        console.rule("[bold green]Phase 1: The Extractor[/bold green]")
        extractor = SmartExtractor()
        df = extractor.run(self.resumes_dir, self.candidates_parquet)
        if df is not None:
            console.print(f"[bold green]✅ Extracted {len(df)} unique candidates.[/bold green]")

    def run_scout(self):
        console.rule("[bold cyan]Phase 2: The Scout[/bold cyan]")
        
        if not self.candidates_parquet.exists():
            console.print("[bold red]❌ Phase 1 data missing. Run Extractor first.[/bold red]")
            return

        # Load Battle Sheet Text (Simulated or Real)
        if self.battle_sheet_path.exists():
            with open(self.battle_sheet_path, 'r') as f:
                data = json.load(f)
                # Combine fields into a rich query vector text
                criteria_text = f"{data.get('role', '')} {data.get('must_haves', '')} {data.get('nice_to_haves', '')}"
        else:
            console.print("[yellow]⚠️  Battle Sheet not found. Using default placeholder.[/yellow]")
            criteria_text = "Python Developer with AWS and 5 years experience."

        scout = SmartScout() # Loads Model
        scout.filter_candidates(self.candidates_parquet, criteria_text, self.top50_parquet, top_k=50)

    def run_arbiter(self):
        console.rule("[bold red]Phase 3: The Arbiter[/bold red]")
        
        if not self.top50_parquet.exists():
            console.print("[bold red]❌ Phase 2 data missing. Run Scout first.[/bold red]")
            return

        # Load Battle Sheet
        if not self.battle_sheet_path.exists():
            console.print("[bold red]❌ Battle Sheet JSON required for Arbiter.[/bold red]")
            return
            
        with open(self.battle_sheet_path, 'r') as f:
            sheet = json.load(f)
            
        import pandas as pd
        df = pd.read_parquet(self.top50_parquet)
        
        colosseum = Colosseum(df, sheet)
        top_10_ids = colosseum.run_tournament()
        
        # Save Final
        final_df = colosseum.df[colosseum.df['id'].isin(top_10_ids)].copy()
        final_df['rank'] = final_df['id'].apply(lambda x: top_10_ids.index(x) + 1)
        final_df = final_df.sort_values('rank')
        
        report_path = self.result_dir / "FINAL_REPORT.csv"
        final_df.to_csv(report_path, index=False)
        
        console.print(Panel(f"🏆 [bold]Tournament Complete![/bold]\nTop 10 Saved to: {report_path}", border_style="green"))

    def menu(self):
        self.check_setup()
        while True:
            console.print("\n")
            console.print(Panel("[bold white]Agency Control Tower[/bold white]", style="bold blue"))
            console.print("1. [green]Run Extractor[/green] (PDF -> Text)")
            console.print("2. [cyan]Run Scout[/cyan] (Text -> Top 50)")
            console.print("3. [red]Run Arbiter[/red] (Top 50 -> Ranked Top 10)")
            console.print("4. Run Full Pipeline")
            console.print("q. Quit")
            
            choice = Prompt.ask("Select Option", choices=["1", "2", "3", "4", "q"])
            
            if choice == "1": self.run_extractor()
            elif choice == "2": self.run_scout()
            elif choice == "3": self.run_arbiter()
            elif choice == "4":
                self.run_extractor()
                self.run_scout()
                self.run_arbiter()
            elif choice == "q":
                sys.exit()

if __name__ == "__main__":
    app = AgencyControl()
    app.menu()