import json
import pandas as pd
from pathlib import Path
from rich.progress import track
from sentence_transformers import CrossEncoder
import re

class ReRanker:
    def __init__(self):
        print("⚖️  Loading Cross-Encoder (MS-MARCO)...")
        self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    def _apply_roi_bonus(self, text, nice_to_haves):
        text_lower = text.lower()
        bonus = 0.0
        metric_pattern = r'(\d+%)|(\$\d+)|(increased|reduced|optimized|improved|saved|delivered|led|Architected|Deployed|Migrated|Refactored|Integrated|Automated|Spearheaded|Orchestrated|Generated|Scaled|Transformed|Pioneered|Mentored|Collaborated|Coached|Onboarded|Cultivated|Negotiated|Authored|Produced|Implemented|Resolved)'
        has_metric = re.search(metric_pattern, text_lower)
        found_skills = [s.lower() for s in nice_to_haves if s.lower() in text_lower]
        
        if has_metric and found_skills:
            bonus += 0.75 
        return bonus

    def _apply_cultural_bonus(self, text, cultural_vibe):
        text_lower = text.lower()
        vibe_keywords = [w.lower() for w in cultural_vibe.split() if len(w) > 3]
        matches = sum(1 for word in vibe_keywords if word in text_lower)
        return matches * 0.15

    def _apply_deal_breaker_penalty(self, text, deal_breakers, keywords_for_scan):
        text_lower = text.lower()
        anchors = [k.lower() for k in keywords_for_scan]
        if not anchors: return 0.0
        found_anchors = sum(1 for a in anchors if a in text_lower)
        coverage = found_anchors / len(anchors)
        if coverage < 0.3: return -3.0 
        return 0.0

    def _extract_keywords(self, text_list):
        kws = []
        for s in text_list:
            kws.extend(re.findall(r'([A-Z0-9][a-zA-Z0-9\.]+|[a-z0-9]+\.[a-z]+)', s))
        return [k.lower() for k in set(kws)]

    # def _evaluate_requirements(self, text, must_haves, deal_breakers):
    #     text_lower = text.lower()
    #     penalty = 0.0
    #     required_entities = self._extract_keywords(must_haves)
    #     if required_entities:
    #         matches = sum(1 for entity in required_entities if entity in text_lower)
    #         coverage = matches / len(required_entities)
    #         if coverage < 0.4: penalty -= 3.0
    #     for db in deal_breakers:
    #         if "no " in db.lower() or "lack of" in db.lower():
    #             subject = db.lower().replace("no ", "").replace("lack of ", "")
    #             if subject not in text_lower: penalty -= 1.0
    #     return penalty

    def _evaluate_requirements(self, text, must_haves, deal_breakers):
        text_lower = text.lower()
        penalty = 0.0
        
        # 1. DYNAMIC 'MUST-HAVE' ASSASSINATION
        # This takes whatever the JSON says is mandatory (e.g., ServSafe)
        for requirement in must_haves:
            # We normalize the requirement into a searchable keyword
            # e.g., "ServSafe or State-level Certification" -> ["servsafe", "certification"]
            req_keywords = self._extract_keywords([requirement])
            
            # If NONE of the keywords for a specific Must-Have are found:
            if not any(k in text_lower for k in req_keywords):
                penalty -= 10.0
                print(f"   🚩 FATAL: Missing mandatory requirement: {requirement}")

        # 2. THE 'DEAL-BREAKER' SNIPER
        for db in deal_breakers:
            # If the JSON says "No valid food safety certification"
            # and the text is missing those keywords:
            if "no " in db.lower() or "lack of" in db.lower():
                subject = db.lower().replace("no ", "").replace("lack of ", "").strip()
                if subject not in text_lower:
                    penalty -= 15.0 # Higher penalty for explicit Deal-Breakers
                    
        return penalty

    def rerank(self, input_file: Path, output_file: Path, battle_sheet_path: Path, top_k: int = 20):
        df = pd.read_parquet(input_file)
        if df.empty: return []

        with open(battle_sheet_path, 'r') as f:
            sheet = json.load(f)
            
        query = sheet.get('summary_for_vector_search', f"{sheet['role']}")
        nice_to_haves = sheet.get('nice_to_haves', [])
        vibe = sheet.get('cultural_vibe', "")
        anchors = sheet.get('keywords_for_scan', [])

        print(f"⚖️  Re-Ranking {len(df)} candidates for '{sheet['role']}'...")

        sentence_pairs = [[query, doc[:2000]] for doc in df['safe_text']]
        base_scores = self.model.predict(sentence_pairs, show_progress_bar=True)

        final_scores = []
        # Using enumerate to avoid indexing bugs 
        for idx, (i, row) in enumerate(df.iterrows()):
            text = row['safe_text']
            score = base_scores[idx] # Corrected from base_scores[i] 
            
            score += self._apply_roi_bonus(text, nice_to_haves)
            score += self._apply_cultural_bonus(text, vibe)
            score += self._apply_deal_breaker_penalty(text, sheet.get('deal_breakers', []), anchors)
            score += self._evaluate_requirements(text, sheet.get('must_haves', []), sheet.get('deal_breakers', []))
            
            final_scores.append(score)

        df['rerank_score'] = final_scores
        top_df = df.sort_values(by='rerank_score', ascending=False).head(top_k)
        top_df.to_parquet(output_file, index=False)
        
        print(f"✅ Re-Ranking Complete. Saved to {output_file}")
        return top_df