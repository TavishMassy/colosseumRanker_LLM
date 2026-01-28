import json
import pandas as pd
from pathlib import Path
from rich.progress import track
from sentence_transformers import CrossEncoder

class ReRanker:
    def __init__(self):
        print("⚖️  Loading Cross-Encoder (MS-MARCO)...")
        # This model is the industry standard for re-ranking
        self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    def rerank(self, input_file: Path, output_file: Path, battle_sheet_path: Path, top_k: int = 20):
        # 1. Load Data
        if not input_file.exists():
            print(f"❌ Input file not found: {input_file}")
            return None
            
        df = pd.read_parquet(input_file)
        if df.empty: return []

        # 2. Load Battle Sheet (The "Query")
        with open(battle_sheet_path, 'r') as f:
            sheet = json.load(f)
            # Combine Role + Must Haves for a strong signal
            query = f"{sheet['role']} {sheet['must_haves']}"

        print(f"⚖️  Re-Ranking {len(df)} candidates against: '{sheet['role']}'...")

        # 3. Prepare Pairs [Query, Candidate_Text]
        # We truncate text to 512 tokens approx (2000 chars) for speed
        sentence_pairs = [[query, doc[:2000]] for doc in df['safe_text']]

        # 4. Score (This is the magic step)
        # The model outputs a float score (higher is better)
        scores = self.model.predict(sentence_pairs, show_progress_bar=True)
        
        # 5. Sort and Cut
        df['rerank_score'] = scores
        df = df.sort_values(by='rerank_score', ascending=False)
        
        # Keep only Top K (e.g., 20)
        top_df = df.head(top_k)
        
        # 6. Save
        top_df.to_parquet(output_file, index=False)
        
        print(f"✅ Re-Ranking Complete.")
        print(f"   📉 Reduced {len(df)} -> {len(top_df)} candidates.")
        print(f"   💾 Saved to: {output_file}")
        
        return top_df

if __name__ == "__main__":
    # Test run
    ranker = ReRanker()
    ranker.rerank(
        Path("data/result/candidates_scouted.parquet"),
        Path("data/result/candidates_reranked.parquet"),
        Path("data/battle_sheet.json"),
        top_k=20
    )