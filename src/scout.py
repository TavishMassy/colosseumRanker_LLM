import re
import spacy
import pandas as pd
from pathlib import Path
from collections import Counter
from rich.progress import track
from urlextract import URLExtract
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Removed: numpy (pandas/sklearn handle the math), os (not needed with pathlib)

class SmartScout:
    def __init__(self, model_name='all-MiniLM-L6-v2') -> None:
        print("🔭 Scout: Loading Neural Network...")
        self.model = SentenceTransformer(model_name)
        self.url_extractor = URLExtract()
        # Optimized spaCy loading - disabling heavy components immediately
        try:
            self.nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "lemmatizer"])
        except OSError:
            print("Installing spaCy model...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm", disable=["ner", "parser", "lemmatizer"])

    def _extract_and_mask(self, text):
        if not text: return text, {"emails": [], "links": []}

        metadata = {"emails": [], "links": []}
        
        # 1. Emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        metadata['emails'] = list(set(re.findall(email_pattern, text)))   
        masked_text = re.sub(email_pattern, "{EMAIL.}", text)

        # 2. Links
        links = list(set(self.url_extractor.find_urls(masked_text)))
        metadata['links'] = links
        for link in sorted(links, key=len, reverse=True):
            masked_text = masked_text.replace(link, "{LINK.}")

        return masked_text, metadata

    def filter_candidates(self, parquet_file, battle_sheet_text, output_file,
                          top_k=50, anchors=None, extract_all=False) -> pd.DataFrame:
        """
        Refined Filter: Handles vector similarity + Density Audit + Anchor check.
        """
        if not Path(parquet_file).exists():
            print(f"❌ Error: {parquet_file} not found.")
            return None
            
        df = pd.read_parquet(parquet_file)
        if df.empty:
            print("⚠️ Warning: No candidates to filter.")
            return df

        print(f"⚔️ Scout: Analyzing {len(df)} candidates...")

        # 2. Vectorization
        query_vector = self.model.encode([battle_sheet_text])
        candidate_vectors = self.model.encode(df['raw_text'].tolist(), show_progress_bar=True)
        scores = cosine_similarity(query_vector, candidate_vectors)[0]

        # 3. Apply Scout Rules
        final_scores = []
        for i, row in df.iterrows():
            text = row['raw_text']
            base_score = scores[i]
            
            # RULE 1: Anchor Keyword Check (Fixed: anchors was ghost code)
            if anchors and not any(a.lower() in text.lower() for a in anchors):
                base_score = 0.0
            
            # RULE 2: Density Audit (Skill-Soup Trap)
            if base_score > 0:
                doc = self.nlp(text[:1500]) # Audit first 1500 chars only
                pos_counts = Counter([token.pos_ for token in doc])
                total_words = sum(pos_counts.values())
                noun_count = pos_counts.get('NOUN', 0) + pos_counts.get('PROPN', 0)
                
                if total_words > 0 and (noun_count / total_words) > 0.40:
                    base_score *= 0.5 
            
            final_scores.append(base_score)

        df['vector_score'] = final_scores

        # 4. Processing Pool (Fixed: extract_all was ghost code)
        target_df = df.sort_values(by='vector_score', ascending=False)
        if not extract_all:
            target_df = target_df.head(top_k).copy()
        else:
            target_df = target_df.copy()

        # 5. Metadata Append Loop
        emails, links, safe_texts = [], [], []

        for idx, row in track(target_df.iterrows(), total=len(target_df), description="Scouting..."):
            safe, meta = self._extract_and_mask(row['raw_text'])
            safe_texts.append(safe)
            emails.append(meta['emails'])
            links.append(meta['links'])

        target_df['safe_text'] = safe_texts
        target_df['emails'] = emails
        target_df['links'] = links
        
        target_df.to_parquet(output_file, index=False)
        print(f"✅ Scout Complete. Saved to '{output_file}'")
        return target_df