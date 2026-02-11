import pandas as pd
import json
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

class DataPackGenerator:
    def __init__(self, result_dir: Path):
        self.result_dir = result_dir
        self.reranked_file = result_dir / "candidates_reranked.parquet"
        self.enriched_file = result_dir / "enriched_report.json"
        self.output_csv = result_dir / "Client_Data_Pack.csv"

    def _clean_field(self, val):
        """Robust cleaner for CSV export."""
        if val is None or pd.isna(val): return "N/A"
        if isinstance(val, (list, tuple, np.ndarray)):
            # Flatten lists/arrays into pipe-separated strings
            # Handle ndarray tolist() if needed
            if hasattr(val, 'tolist'): val = val.tolist()
            return " | ".join(map(str, val))
        return str(val).strip()

    def generate(self):
        console.print(Panel("[bold blue]Phase 8: Generating Executive Data Pack[/bold blue]", border_style="blue"))
        
        # STRATEGY: Prefer Enriched JSON (Phase 7) > Reranked Parquet (Phase 4)
        if self.enriched_file.exists():
            console.print("[green]✨ Found Enriched Audit Data (JSON). Generating full report...[/green]")
            self._generate_from_json()
        elif self.reranked_file.exists():
            console.print("[yellow]⚠️ Audit not run yet. Generating preliminary report from Re-Ranker...[/yellow]")
            self._generate_from_parquet()
        else:
            console.print("[red]❌ No candidate data found. Run Phase 1, 4, or 7 first.[/red]")

    def _generate_from_json(self):
        """Generates CSV from the final Auditor JSON (Contains all new fields)."""
        try:
            with open(self.enriched_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert list of dicts to DataFrame
            df = pd.DataFrame(data)
            
            # Select and Rename Columns for Client View
            # We explicitly map the new "Time-to-Fill" fields
            client_columns = {
                'Rank': 'Rank',
                'Name': 'Candidate Name',
                'Risk Level': 'Risk Level',
                'Risk Flag': 'Risk Flag',  # <--- New Field
                'Reason': 'Audit Notes',
                'Current Company': 'Current Company', # <--- New Field
                'Notice Period': 'Notice Period',     # <--- New Field
                'Location': 'Location',
                'Years Exp': 'Experience',
                'Email': 'Email',
                'Phone': 'Phone',
                'Links': 'Links',
                'Key Skills': 'Detected Skills',
                'Professional Summary': 'Summary',
                'Battle Narrative': 'Auditor Verdict',
                'file_name': 'Source File'
            }
            
            # Ensure columns exist even if JSON is partial
            for col in client_columns.keys():
                if col not in df.columns:
                    df[col] = "N/A"
            
            # Reorder and Rename
            export_df = df[list(client_columns.keys())].rename(columns=client_columns)
            
            # Clean Lists for CSV
            for col in export_df.columns:
                export_df[col] = export_df[col].apply(self._clean_field)
            
            export_df.to_csv(self.output_csv, index=False)
            self._print_success(len(export_df), "Enriched Audit (Phase 7)")
            
        except Exception as e:
            console.print(f"[red]❌ Error reading JSON: {e}[/red]")

    def _generate_from_parquet(self):
        """Generates CSV from the raw Parquet (Limited fields)."""
        try:
            df = pd.read_parquet(self.reranked_file)
            final_rows = []
            
            for _, row in df.iterrows():
                # Extract partial metadata from Phase 1/4
                meta = {}
                if 'metadata' in row and row['metadata']:
                    try: meta = json.loads(row['metadata'])
                    except: pass
                
                final_rows.append({
                    'Rank': 'N/A (Run Audit)',
                    'Candidate Name': meta.get('full_name') or "Unknown",
                    'Match Score': round(row.get('rerank_score', 0), 2),
                    'Email': self._clean_field(row.get('emails')),
                    'Phone': self._clean_field(row.get('phones')),
                    'Links': self._clean_field(row.get('links')),
                    'Skills': row.get('regex_skills', ''),
                    'Source File': row.get('file_name', 'N/A')
                })
            
            export_df = pd.DataFrame(final_rows)
            export_df.to_csv(self.output_csv, index=False)
            self._print_success(len(export_df), "Raw Re-Ranker (Phase 4)")
            
        except Exception as e:
            console.print(f"[red]❌ Error reading Parquet: {e}[/red]")

    def _print_success(self, count, source):
        console.print(Panel(
            f"✅ [bold green]Data Pack Generated![/bold green]\n"
            f"📂 Path: {self.output_csv}\n"
            f"📊 Candidates: {count}\n"
            f"🧬 Source: {source}", 
            border_style="green"
        ))

if __name__ == "__main__":
    DataPackGenerator(Path("data/result")).generate()