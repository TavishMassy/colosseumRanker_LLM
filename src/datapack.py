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
        self.enriched_file = result_dir / "enriched_report.json"
        self.reranked_file = result_dir / "candidates_reranked.parquet"
        self.scouted_file = result_dir / "candidates_scouted.parquet"
        self.output_csv = result_dir / "Client_Data_Pack.csv"

    def _clean_field(self, val):
        """Robust cleaner for CSV export."""
        if val is None: return "N/A"
        if isinstance(val, (list, tuple, np.ndarray)):
            if hasattr(val, 'tolist'): val = val.tolist()
            clean_list = [str(x) for x in val if x and str(x).lower() != 'none']
            return " | ".join(clean_list) if clean_list else "N/A"
        return str(val).strip()

    def generate(self):
        try: 
            if self.output_csv.exists():
                console.print(f'[red] Existing data pack found. Removing old file... [/red]')
                self.output_csv.unlink()
        except Exception as e:
            console.print(f'[red] Error while removing existing file: {e} [/red]')
            return 

        # 1. Load the "Best Available" Qualified Data
        base_df = pd.DataFrame()
        source_name = "None"

        if self.enriched_file.exists():
            base_df = self._load_json()
            source_name = "Enriched Audit"
        elif self.reranked_file.exists():
            base_df = self._load_reranked()
            source_name = "Re-Ranker"
        
        # 2. Load the Raw Scouted Data (The "Unqualified" pool)
        if self.scouted_file.exists():
            scouted_df = pd.read_parquet(self.scouted_file)
            console.print(f"[cyan]system: Merging {len(scouted_df)} total leads from scouted data...[/cyan]")
            
            # 3. Identify and Append missing candidates
            final_df = self._merge_unqualified(base_df, scouted_df)
        else:
            console.print("[yellow]⚠️ Scouted file not found. Exporting qualified only.[/yellow]")
            final_df = base_df

        # 4. Final Cleanup and Export
        if not final_df.empty:
            for col in final_df.columns:
                final_df[col] = final_df[col].apply(self._clean_field)
            
            final_df.to_csv(self.output_csv, index=False)
            self._print_success(len(final_df), f"{source_name} + Unqualified Fallback")
        else:
            console.print("[red]❌ No data found to export.[/red]")

    def _merge_unqualified(self, qualified_df, scouted_df):
        """Appends candidates from scouted_df that aren't in qualified_df."""
        
        # Standardize scouted columns to match the output format
        scouted_clean = pd.DataFrame({
            'Rank': 'Unqualified',
            'Candidate Name': scouted_df.get('full_name', 'N/A'),
            'Risk Level': 'N/A',
            'Email': scouted_df.get('emails'),
            'Phone': scouted_df.get('phones'),
            'Links': scouted_df.get('links'),
            'Detected Skills': scouted_df.get('regex_skills'),
            'Source File': scouted_df.get('file_name', 'N/A')
        })

        if qualified_df.empty:
            return scouted_clean

        # Filter out candidates already present in the qualified list (by Name or Email)
        # This prevents duplicates
        existing_names = qualified_df['Candidate Name'].unique()
        unqualified_only = scouted_clean[~scouted_clean['Candidate Name'].isin(existing_names)]
        
        # Combine
        combined = pd.concat([qualified_df, unqualified_only], ignore_index=True)
        return combined

    def _load_json(self):
        """Loads Phase 7 Data."""
        with open(self.enriched_file, 'r', encoding='utf-8') as f:
            df = pd.DataFrame(json.load(f))
        
        mapping = {
            'Rank': 'Rank', 'Name': 'Candidate Name', 'Risk Level': 'Risk Level',
            'Email': 'Email', 'Phone': 'Phone', 'Links': 'Links', 
            'Key Skills': 'Detected Skills', 'file_name': 'Source File'
        }
        # Ensure columns exist
        for col in mapping.keys():
            if col not in df.columns: df[col] = "N/A"
            
        return df[list(mapping.keys())].rename(columns=mapping)

    def _load_reranked(self):
        """Loads Phase 4 Data."""
        df = pd.read_parquet(self.reranked_file)
        # Flattening logic for Phase 4 metadata if needed
        return pd.DataFrame({
            'Rank': 'Pending Audit',
            'Candidate Name': df.get('full_name', 'Unknown'),
            'Risk Level': 'N/A',
            'Email': df.get('emails'),
            'Phone': df.get('phones'),
            'Links': df.get('links'),
            'Detected Skills': df.get('regex_skills'),
            'Source File': df.get('file_name', 'N/A')
        })

    def _print_success(self, count, source):
        console.print(Panel(
            f"✅ [bold green]Full Data Pack Generated![/bold green]\n"
            f"📂 Path: {self.output_csv}\n"
            f"📊 Total Entries: {count}\n"
            f"🧬 Blend: {source}", 
            border_style="green"
        ))

if __name__ == "__main__":
    DataPackGenerator(Path("data/result")).generate()