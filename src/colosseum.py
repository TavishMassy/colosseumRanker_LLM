import os
import time
import json
import random
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from rich.progress import Progress
from playwright.sync_api import sync_playwright

# Import the Engine
from src.engine import Engine

# --- CONFIGURATION ---
DATA_DIR = Path("data")
PROMPTS_DIR = DATA_DIR / "prompts"
RESULT_DIR = DATA_DIR / "result"

# For jr/mid level roles and 5000 for senior ones
RESUME_SIZE = 3000

# Only these candidates get sorted. Everyone else fights the Gatekeeper.
WINNERS_CIRCLE_SIZE = 10

class FactChecker:
    def __init__(self) -> None:
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def scrape_text(self, url) -> str:
        """Launches a browser to extract visible text from a website."""
        # Skip social media - anti-scraping is too high and text isn't useful for 'evidence'
        if any(domain in url.lower() for domain in ["linkedin.com", "twitter.com", "facebook.com"]):
            return f"Social Profile Verified: {url}"

        try:
            with sync_playwright() as p:
                # Use a real browser to handle React/Vue/Next.js portfolios
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate and wait until the network is quiet (10s timeout)
                page.goto(url, wait_until="networkidle", timeout=10000)
                
                # Extract text from the body to avoid <script> and <style> tags
                raw_text = page.inner_text("body")
                
                # Clean up whitespace and limit length to avoid 'Token Bloat' in the AI
                clean_text = " ".join(raw_text.split())
                browser.close()
                
                return f"SCRAPED CONTENT: {clean_text[:1500]}..." # First 1500 chars is plenty
        except Exception as e:
            return f"Scrape Failed ({str(e)[:30]})"

class Colosseum:
    def __init__(self, candidates_df, battle_sheet) -> None:
        self.df = candidates_df.copy()

        if (RESULT_DIR / "candidates_processed.parquet").exists():            
            self.df_processed = pd.read_parquet(RESULT_DIR / "candidates_processed.parquet")
        else:
            self.df_processed = None

        self.sheet = battle_sheet
        self.investigator = FactChecker()
        
        # Initialize the Engine
        self.engine = Engine()
        
        self.prompts = {
            # "newcomer": self._load_prompt("judge_newcomer.txt"),
            # "gatekeeper": self._load_prompt("judge_gatekeeper.txt"),
            "ranker": self._load_prompt("judge_ranker.txt")
        }

        # Ensure columns exist
        if 'battle_log' not in self.df.columns:
            self.df['battle_log'] = [[] for _ in range(len(self.df))]
        if 'rerank_score' not in self.df.columns:
            self.df['rerank_score'] = 0.5

    def _load_prompt(self, filename) -> str:
        path = PROMPTS_DIR / filename
        if not path.exists():
            # Fallback
            raise FileNotFoundError(f"❌ Prompt template not found at: {path}")
        with open(path, 'r') as f:
            return f.read()

    def _ensure_evidence(self, candidate_id) -> None:
        # 1. Prevent KeyError: Check if column exists, create if not
        if 'evidence' not in self.df.columns:
            self.df['evidence'] = ""

        idx_list = self.df.index[self.df['id'] == candidate_id].tolist()
        if not idx_list: return
        idx = idx_list[0]

        # 2. Skip if already processed
        current_val = self.df.at[idx, 'evidence']
        if pd.notna(current_val) and current_val != "":
            return

        # 3. Handle contact_info safely
        contact_info = self.df.at[idx, 'contact_info']
        if isinstance(contact_info, str):
            try:
                contact_info = json.loads(contact_info)
            except:
                contact_info = {}
        
        # Ensure contact_info is a dict
        if not isinstance(contact_info, dict):
            contact_info = {}

        # 4. Extract links (handling both list and numpy/pandas series)
        raw_links = contact_info.get('links', [])
        if isinstance(raw_links, (list, tuple)):
            links = list(raw_links)
        elif hasattr(raw_links, 'tolist'): # Handle numpy/pandas types
            links = raw_links.tolist()
        else:
            links = []

        if not links:
            self.df.at[idx, 'evidence'] = "No links provided."
            return

        # 5. Link Scraping Pass
        print(f"   🔎 {candidate_id[:6]}: Deep-scanning portfolio content...")
        evidence_list = []
        
        for link in links:
            if not isinstance(link, str) or not link.startswith('http'):
                continue
            
            # CALL THE NEW SCRAPER
            content = self.investigator.scrape_text(link)
            evidence_list.append(f"SOURCE [{link}]: {content}")
            
        if evidence_list:
            self.df.at[idx, 'evidence'] = " | ".join(evidence_list)
        else:
            self.df.at[idx, 'evidence'] = "No valid portfolio data found."
            
        print(f"   ✅ Evidence Logged.")

    def purge_high_risk(self):
        """Disqualifies candidates flagged as High Risk by the Auditor."""
        print(f"🛡️  Security Sweep: Auditing candidate risk levels...")
        
        disqualified_count = 0
        
        for idx, row in self.df.iterrows():
            meta = {}
            if 'metadata' in row and pd.notna(row['metadata']):
                try:
                    meta = json.loads(row['metadata'])
                except:
                    pass
            
            # 🚨 DISQUALIFICATION TRIGGER
            if meta.get('risk') == "High":
                reason = meta.get('risk_reason', 'Flagged by security audit')
                self._log_event(row['id'], f"🚫 DISQUALIFIED: {reason}")
                # Move them to a rank that is impossible to reach (e.g., 999)
                self.df.at[idx, 'rank'] = 999 
                disqualified_count += 1
        
        # Remove them from the active queue for the run_tournament loop
        self.df = self.df[self.df['rank'] != 999].reset_index(drop=True)
        print(f"✅ Sweep Complete: {disqualified_count} high-risk candidates removed.")

    def _get_dossier(self, candidate_id) -> str:
        self._ensure_evidence(candidate_id)
        row = self.df.loc[self.df['id'] == candidate_id].iloc[0]
        return f"ID: {row['id']}\nRESUME CONTENT: {row['safe_text'][:RESUME_SIZE]}\nVERIFIED LINKS: {row['evidence']}"

    def _battle(self, id_a, id_b, mode="gatekeeper"):
        role_context = f"""
        ROLE: {self.sheet.get('role')}
        MUST-HAVES: {self.sheet.get('must_haves')}
        NICE-TO-HAVES: {self.sheet.get('nice_to_haves', [])}
        DEAL-BREAKERS: {self.sheet.get('deal_breakers', [])}
        CULTURE: {self.sheet.get('cultural_vibe', 'Standard')}
        Location Preference: {self.sheet.get('location_preference', 'Any')}
        """
        
        prompt_template = self.prompts['ranker']

        prompt = prompt_template.replace("{{role}}", role_context)
        prompt = prompt.replace("{{text_a}}", self._get_dossier(id_a))
        prompt = prompt.replace("{{text_b}}", self._get_dossier(id_b))
        
        result = self.engine.think(prompt)

        if not result:
            print(f"\n🚨 [CRITICAL ERROR] The AI Engine is unresponsive.")
            # Default to A winning to prevent crash, but log it
            return {"winner_id": id_b, "reason": "AI Failed, Default Win to Gatekeeper."}

        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        return result

    def _log_event(self, cand_id, message):
        """Finds the candidate by ID and appends a message to their battle log."""
        indices = self.df.index[self.df['id'] == cand_id].tolist()
        if not indices: return
        idx = indices[0]
        
        current_log = self.df.at[idx, 'battle_log']
        if not isinstance(current_log, list):
            current_log = []
        current_log.append(message)
        self.df.at[idx, 'battle_log'] = current_log

    def _find_insertion_index(self, candidate_id, ranked_list) -> int:
        """
        Uses Binary Search Battles to find the EXACT spot for a candidate.
        Returns the INDEX where the candidate should be inserted.
        """
        low = 0
        high = len(ranked_list) - 1
        
        while low <= high:
            mid = (low + high) // 2
            opponent_id = ranked_list[mid]
            
            print(f"   ⚔️  Fighting Rank #{mid+1} ({opponent_id[:6]})...")
            
            outcome = self._battle(candidate_id, opponent_id, mode="ranker")
            winner = outcome.get('winner_id')
            reason = outcome.get('reason', 'No reason')

            if winner == candidate_id:
                # Challenger WON. They belong higher (lower index).
                self._log_event(candidate_id, f"✅ BEAT Rank #{mid+1} ({opponent_id[:6]}): {reason[:50]}...")
                self._log_event(opponent_id, f"❌ LOST to Challenger ({candidate_id[:6]}): {reason[:50]}...")
                high = mid - 1
            else:
                # Challenger LOST. They belong lower (higher index).
                self._log_event(candidate_id, f"❌ LOST to Rank #{mid+1} ({opponent_id[:6]}): {reason[:50]}...")
                self._log_event(opponent_id, f"🛡️ DEFENDED against ({candidate_id[:6]}): {reason[:50]}...")
                low = mid + 1
                
        return low

    def run_tournament(self, test_mode=False) -> list:
        self.purge_high_risk()

        candidates = self.df['id'].tolist()
        if not candidates:
            print("[red]❌ No candidates to fight![/red]")
            return []

        # CONSTANT: The size of the "Winner's Circle"
        
        print(f"🏟️  The Colosseum is Open. {len(candidates)} candidates queuing...")
        print(f"🛡️  Winner's Circle Size: {WINNERS_CIRCLE_SIZE}")
        
        ranked_list = []

        with Progress() as progress:
            task = progress.add_task("[red]⚔️  Tournament in Progress...", total=len(candidates))

            for newcomer_id in candidates:
                cand_name = newcomer_id[:6]
                
                # --- BUILD THE LIST ---
                if len(ranked_list) < WINNERS_CIRCLE_SIZE:
                    if not ranked_list:
                        ranked_list.append(newcomer_id)
                        self._log_event(newcomer_id, "🏁 First Entrant (Seeded #1)")
                    else:
                        print(f"\n🚪 {cand_name} entering...")
                        insert_pos = self._find_insertion_index(newcomer_id, ranked_list)
                        ranked_list.insert(insert_pos, newcomer_id)
                        
                        rank_display = insert_pos + 1
                        self._log_event(newcomer_id, f"🏅 Placed at Rank #{rank_display}")

                # --- GATEKEEPER MODE (>= 10) ---
                else:
                    gatekeeper_id = ranked_list[-1] # The person at Rank #10
                    print(f"\n🛡️  Gatekeeper Challenge: {cand_name} vs Rank #{WINNERS_CIRCLE_SIZE} ({gatekeeper_id[:6]})")
                    
                    outcome = self._battle(newcomer_id, gatekeeper_id, mode="gatekeeper")
                    winner = outcome.get('winner_id')
                    reason = outcome.get('reason', 'No reason')

                    if winner == gatekeeper_id:
                        # REJECTED
                        self._log_event(newcomer_id, f"❌ REJECTED by Gatekeeper: {reason[:50]}...")
                        self._log_event(gatekeeper_id, f"🛡️ DEFENDED spot against {cand_name}")
                        print(f"   🚫 Rejected.")
                        
                    else:
                        # ACCEPTED -> OLD #10 FIRED
                        self._log_event(gatekeeper_id, f"💀 ELIMINATED by Newcomer {cand_name}: {reason[:50]}...")
                        self._log_event(newcomer_id, f"⚔️  KILLED the Gatekeeper. Entering Ranking Phase...")
                        print(f"   ✅ Gatekeeper Defeated! Ranking {cand_name} now...")
                        
                        ranked_list.pop() # Bye #10
                        
                        # Find specific rank
                        insert_pos = self._find_insertion_index(newcomer_id, ranked_list)
                        ranked_list.insert(insert_pos, newcomer_id)
                        
                        rank_display = insert_pos + 1
                        self._log_event(newcomer_id, f"🏅 Placed at Rank #{rank_display}")
                        print(f"   🏅 Placed at Rank #{rank_display}")

                # Save Periodically
                if len(ranked_list) % 3 == 0:
                    self.df.to_parquet(RESULT_DIR / "candidates_processed.parquet", index=False)
                
                progress.update(task, advance=1)
                
                if test_mode and len(ranked_list) >= 3: break

        # --- FINAL SORT & SAVE ---
        print("\n🧹 Finalizing Ranks & Sorting...")
        
        # 1. Map Top 10 to Ranks 1-10
        rank_map = {cid: i for i, cid in enumerate(ranked_list, 1)}

        # 2. Identify candidates NOT in the Top 10
        remaining_candidates = self.df[~self.df['id'].isin(ranked_list)].copy()

        # 3. Sort: Rank 1, 2.. 10, 11....
        for i, (idx, row) in enumerate(remaining_candidates.iterrows(), start=WINNERS_CIRCLE_SIZE + 1):
            rank_map[row['id']] = i     
            
        # 4. Apply the map and sort
        self.df['rank'] = self.df['id'].map(rank_map).astype(int)
        self.df = self.df.sort_values('rank', ascending=True)

        return ranked_list