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
        self.output_csv = result_dir / "Data_Pack.csv"

    def _clean_list_safe(self, val):
        """
        Robust cleaner that handles Lists, NumPy Arrays, strings, and NaNs
        without triggering 'Ambiguous Truth Value' errors.
        """
        # 1. Handle None/NaN immediately
        if val is None: 
            return "N/A"
        
        # 2. Handle Lists and Tuples
        if isinstance(val, (list, tuple)):
            if len(val) == 0: return "N/A"
            return " | ".join(map(str, val))
        
        # 3. Handle NumPy Arrays (The common crasher)
        if hasattr(val, 'size'):
            if val.size == 0: return "N/A"
            # Flatten and convert
            if hasattr(val, 'tolist'):
                return " | ".join(map(str, val.tolist()))
            return str(val)

        # 4. Handle Strings & Parsing
        s_val = str(val).strip()
        
        # Catch stringified empty lists or NaNs
        if s_val in ["", "[]", "nan", "None", "N/A"]: 
            return "N/A"
            
        return s_val.strip("[]'\" ")

    def generate(self):
        console.print(Panel("[bold blue]Phase 8: Generating Executive Data Pack[/bold blue]", border_style="blue"))
        
        # 1. Source Selection
        if self.reranked_file.exists():
            input_path, tag = self.reranked_file, "Preliminary Metadata (Pre-Tournament)"
        else:
            console.print("[red]❌ No candidate data found. Run Phase 1 or 4 first.[/red]")
            return

        try:
            df = pd.read_parquet(input_path)
        except Exception as e:
            console.print(f"[red]❌ Error reading parquet file: {e}[/red]")
            return

        final_rows = []

        # 2. Iteration & Normalization
        for _, row in df.iterrows():
            # Extract Metadata
            meta = {}
            if 'metadata' in row:
                val = row['metadata']
                if pd.notna(val) and val:
                    try:
                        meta = json.loads(val) if isinstance(val, str) else val
                    except: pass
            
            # Normalize Score (0.000 - 1.000)
            raw_score = row.get('rerank_score', 0)
            try:
                norm_score = round(max(0, min(1, (float(raw_score) + 10) / 20)), 3)
            except:
                norm_score = 0.000

            # Build Row
            candidate_data = {
                'Candidate Name': meta.get('full_name') or row.get('file_name', 'Unknown'),
                'Risk Level': meta.get('risk', 'Low'),
                'Experience': f"{meta.get('yoe', 0)} Yrs",
                'Location': meta.get('location', 'N/A'),
                
                # SAFE CLEANING APPLIED HERE
                'Email': self._clean_list_safe(row.get('emails', meta.get('email'))),
                'Phone': self._clean_list_safe(row.get('phones', meta.get('phone'))),
                'Links': self._clean_list_safe(row.get('links', meta.get('link'))),
                
                'Top Skills': row.get('regex_skills', 'N/A'),
                'Risk Audit': meta.get('reason', 'No flags identified.'),
                'File Reference': row.get('file_name', 'N/A')
            }
            final_rows.append(candidate_data)

        # 3. Export
        export_df = pd.DataFrame(final_rows)

        # Intelligent Sorting
        if 'Rank' in export_df.columns:
            # Convert to numeric, coerce errors to NaN, fill with 999 for sorting
            ranks = pd.to_numeric(export_df['Rank'], errors='coerce').fillna(999)
            export_df['temp_rank'] = ranks
            export_df = export_df.sort_values('temp_rank').drop(columns=['temp_rank'])
        else:
            export_df = export_df.sort_values('AI Score', ascending=False)

        export_df.to_csv(self.output_csv, index=False)

        console.print(Panel(
            f"✅ [bold green]Data Pack Generated![/bold green]\n"
            f"📂 Path: {self.output_csv}\n"
            f"📊 Candidates: {len(export_df)}\n"
            f"🧬 Context: {tag}", 
            border_style="green"
        ))

if __name__ == "__main__":
    # Test run
    DataPackGenerator(Path("data/result")).generate()