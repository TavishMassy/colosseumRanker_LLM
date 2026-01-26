import re
import numpy as np
import pandas as pd
import phonenumbers
from pathlib import Path
from rich.progress import track
from urlextract import URLExtract
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class SmartScout:
    def __init__(self, model_name='all-MiniLM-L6-v2') -> None:
        print("🔭 Scout: Loading Neural Network (this happens once)...")
        # Downloads the model automatically on first run
        self.model = SentenceTransformer(model_name)
        self.url_extractor = URLExtract()

    def _extract_and_mask(self, text):
        """
        Extracts PII (Phone/Email) + Links.
        Returns: 
          - masked_text (for AI)
          - metadata (real email/phone/links for You)
        """
        if not text: return text, {}

        metadata = {
            "emails": [],
            "phones": [],
            "links": []
        }

        # 1. Extract & Mask Emails (Regex is still best for this)
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        metadata['emails'] = list(set(re.findall(email_pattern, text)))
        
        # Mask them in the text
        masked_text = re.sub(email_pattern, "[EMAIL_REDACTED]", text)

        # 2. Extract & Mask Phones (Using Google's lib)
        # Look for matches and replace them securely
        matches = phonenumbers.PhoneNumberMatcher(masked_text, "US") # Default region
        phones = []
        for match in matches:
            phones.append(phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164))
            # Replace using the match's span
            start, end = match.start, match.end
            # A simple replace might hit wrong things, so we handle masking carefully
            # For simplicity in this script, we'll do a second pass or just accept raw regex for masking
            # But since we have the extraction, let's just use a broad regex for masking visual clutter
        
        metadata['phones'] = list(set(phones))
        
        # Broad regex just to hide numbers from the LLM (Bias prevention)
        phone_visual_pattern = r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
        masked_text = re.sub(phone_visual_pattern, "[PHONE_REDACTED]", masked_text)

        # 3. Extract Links (Using urlextract)
        # DO NOT mask links. The AI needs them to know if a portfolio exists.
        # Just extract them so we can Scrape them later.
        metadata['links'] = list(set(self.url_extractor.find_urls(text)))

        return masked_text, metadata

    def filter_candidates(self, parquet_file, battle_sheet_text, output_file, top_k=50) -> list:
        """
        Input: Path to candidates.parquet, Text of the 'Battle Sheet' (Criteria).
        Output: List of the Top 50 Candidate IDs.
        """
        # 1. Load Data
        if not Path(parquet_file).exists():
            print(f"❌ Error: {parquet_file} not found. Run Phase 1 first.")
            return None
            
        df = pd.read_parquet(parquet_file)
        if df.empty:
            print("⚠️ Warning: No candidates to filter.")
            return []
            
        print(f"⚔️  Scout: Analyzing {len(df)} candidates against the Battle Sheet...")

        # 2. Embed the Battle Sheet (The "Target")
        # Assume battle_sheet_text is a string like "Must have Python, AWS, and 3 years exp..."
        query_vector = self.model.encode([battle_sheet_text])

        # 3. Embed the Candidates (The "Pool")
        # fast=True creates embeddings in parallel if possible
        candidate_vectors = self.model.encode(df['raw_text'].tolist(), show_progress_bar=True)

        # 4. Math Time (Cosine Similarity)
        # Result is a matrix of scores (0.0 to 1.0)
        scores = cosine_similarity(query_vector, candidate_vectors)[0]

        # 5. Rank & Cut
        # Add scores to the dataframe temporarily
        df['vector_score'] = scores
        
        # Sort by Score (Descending) and take Top K
        top_candidates = df.sort_values(by='vector_score', ascending=False).head(top_k)
        
        print(f"🕵️  Scout: Refining Top {len(top_candidates)} (Extracting PII & Links)...")

        # 6. The Refinement Loop (Extract & Mask)
        # Apply the extraction ONLY to the survivors
        
        safe_texts = []
        meta_list = []

        for text in track(top_candidates['raw_text'], description="[cyan]Masking PII..."):
            safe, meta = self._extract_and_mask(text)
            safe_texts.append(safe)
            meta_list.append(meta)

        # Save the Clean Data
        top_candidates['safe_text'] = safe_texts
        top_candidates['contact_info'] = meta_list
        
        # Save to a new file for Phase 3
        top_candidates.to_parquet(output_file, index=False)

        print(f"✅ Scout Complete. Top {len(top_candidates)} saved to '{output_file}'")
        return top_candidates