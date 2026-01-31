import sys
import os
import time
import json
import random
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from rich.progress import Progress

# Import the Engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine import Engine

# --- CONFIGURATION ---
DATA_DIR = Path("data")
PROMPTS_DIR = DATA_DIR / "prompts"
RESULT_DIR = DATA_DIR / "result"

# Only these candidates get sorted. Everyone else fights the Gatekeeper.
WINNERS_CIRCLE_SIZE = 10

class FactChecker:
    def __init__(self) -> None:
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def verify_link(self, url) -> str:
        if "linkedin.com" in url or "twitter.com" in url:
             return "Social Profile (Skipped)"
        try:
            time.sleep(random.uniform(0.5, 1.0))
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "No Title"
                return f"Verified Live: {title}"
            elif response.status_code == 404:
                return "Dead Link (404)"
            else:
                return f"Broken Link ({response.status_code})"
        except Exception as e:
            return f"Link Unreachable ({str(e)})"

class Colosseum:
    def __init__(self, candidates_df, battle_sheet) -> None:
        self.df = candidates_df.copy()
        self.sheet = battle_sheet
        self.investigator = FactChecker()
        
        # Initialize the Engine
        self.engine = Engine()
        
        self.prompts = {
            "newcomer": self._load_prompt("judge_newcomer.txt"),
            "gatekeeper": self._load_prompt("judge_gatekeeper.txt"),
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
            return "Compare {{text_a}} and {{text_b}}. Return JSON with winner_id."
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

        # 5. Link Verification Pass
        print(f"   🔎 {candidate_id[:6]}: Found {len(links)} links. Searching...")
        evidence_list = []
        
        # Limit to first 2 links to save time/requests
        for link in links[:2]: 
            if not isinstance(link, str) or not link.startswith('http'):
                continue
            status = self.investigator.verify_link(link)
            evidence_list.append(f"{link} -> {status}")
            
        if evidence_list:
            self.df.at[idx, 'evidence'] = " | ".join(evidence_list)
        else:
            self.df.at[idx, 'evidence'] = "No valid links found."
            
        print(f"   ✅ Evidence Logged.")

    def _get_dossier(self, candidate_id) -> str:
        self._ensure_evidence(candidate_id)
        row = self.df.loc[self.df['id'] == candidate_id].iloc[0]
        return f"ID: {row['id']}\nRESUME CONTENT: {row['safe_text'][:3000]}\nVERIFIED LINKS: {row['evidence']}"

    def _battle(self, id_a, id_b, mode="gatekeeper"):
        role_context = f"""
        ROLE: {self.sheet.get('role')}
        MUST-HAVES: {self.sheet.get('must_haves')}
        NICE-TO-HAVES: {self.sheet.get('nice_to_haves', [])}
        DEAL-BREAKERS: {self.sheet.get('deal_breakers', [])}
        CULTURE: {self.sheet.get('cultural_vibe', 'Standard')}
        Location Preference: {self.sheet.get('location_preference', 'Any')}
        """
        
        if mode == "newcomer":
            prompt_template = self.prompts['newcomer']
        elif mode == "ranker":
            prompt_template = self.prompts['ranker']
        else:
            prompt_template = self.prompts['gatekeeper']

        prompt = prompt_template.replace("{{role}}", role_context)
        prompt = prompt.replace("{{must_haves}}", str(self.sheet.get('must_haves')))
        prompt = prompt.replace("{{text_a}}", self._get_dossier(id_a))
        prompt = prompt.replace("{{text_b}}", self._get_dossier(id_b))
        
        result = self.engine.think(prompt)

        if not result:
            print(f"\n🚨 [CRITICAL ERROR] The AI Engine is unresponsive.")
            # Default to A winning to prevent crash, but log it
            return {"winner_id": id_b, "reason": "AI Failed, Default Win to Gatekeeper."}

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
                
                # --- PHASE 1: BUILD THE LIST (< 10) ---
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

                # --- PHASE 2: GATEKEEPER MODE (>= 10) ---
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
        
        # 2. Assign Ranks. Losers get Rank 999
        self.df['rank'] = self.df['id'].map(rank_map).fillna(999).astype(int)
        
        # 3. Sort: Rank 1, 2... 10... 999, 999
        self.df = self.df.sort_values('rank', ascending=True)
        
        self.df.to_parquet(RESULT_DIR / "candidates_processed.parquet", index=False)
        print(f"✅ Tournament Complete. Top {len(ranked_list)} Survivors sorted at the top.")

        return ranked_list