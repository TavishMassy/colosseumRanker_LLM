import time
import json
import random
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from rich.progress import Progress

# Import the Engine
from src.engine import Engine

# --- CONFIGURATION ---
DATA_DIR = Path("data")
PROMPTS_DIR = DATA_DIR / "prompts"
RESULT_DIR = DATA_DIR / "result"

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
        self.df = candidates_df
        self.sheet = battle_sheet
        self.investigator = FactChecker()
        self.arena = [] 
        self.capacity = 10
        
        # Initialize the Engine
        self.engine = Engine()
        
        self.prompts = {
            "newcomer": self._load_prompt("judge_newcomer.txt"),
            "gatekeeper": self._load_prompt("judge_gatekeeper.txt"),
            "ranker": self._load_prompt("judge_ranker.txt")
        }

    def _load_prompt(self, filename) -> str:
        path = PROMPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"❌ Missing Prompt: {path}")
        with open(path, 'r') as f:
            return f.read()

    def _ensure_evidence(self, candidate_id) -> None:
        idx = self.df.index[self.df['id'] == candidate_id].tolist()[0]
        if self.df.at[idx, 'evidence']: return

        # Get links extracted by Regex/Scout
        contact_info = self.df.at[idx, 'contact_info']
        
        # 1. Safe parsing from JSON string or Dict
        if isinstance(contact_info, str):
            try: contact_info = json.loads(contact_info)
            except: contact_info = {}
        
        # 2. Extract links safely
        raw_links = contact_info.get('links', [])
        
        # 3. CRITICAL FIX: Ensure it is a standard Python list
        if hasattr(raw_links, 'tolist'): # Check if it's a numpy array
            links = raw_links.tolist()
        else:
            links = list(raw_links)

        # 4. Now this check is safe
        if not links:
            self.df.at[idx, 'evidence'] = "No links provided."
            return

        print(f"   🔎 {candidate_id[:6]}: Found {len(links)} links. Searching...")
        
        evidence_list = []
        for link in links[:2]: 
            status = self.investigator.verify_link(link)
            evidence_list.append(f"{link} -> {status}")
            
        print(f"   ✅ Search Result: {evidence_list}")
        self.df.at[idx, 'evidence'] = " | ".join(evidence_list)

    def _get_dossier(self, candidate_id) -> str:
        self._ensure_evidence(candidate_id)
        row = self.df.loc[self.df['id'] == candidate_id].iloc[0]
        # Anonymous Dossier
        return f"ID: {row['id']}\nRESUME CONTENT: {row['safe_text'][:3000]}\nVERIFIED LINKS: {row['evidence']}"

    def _battle(self, id_a, id_b, mode="gatekeeper"):
        """
        FAIL-SAFE BATTLE LOGIC
        """
        # 1. Select Prompt Template
        if mode == "newcomer":
            prompt = self.prompts['newcomer'].replace("{{text_a}}", self._get_dossier(id_a)).replace("{{text_b}}", self._get_dossier(id_b))
        elif mode == "ranker":
            prompt = self.prompts['ranker'].replace("{{text_a}}", self._get_dossier(id_a)).replace("{{text_b}}", self._get_dossier(id_b))
        else:
            prompt = self.prompts['gatekeeper'].replace("{{text_a}}", self._get_dossier(id_a)).replace("{{text_b}}", self._get_dossier(id_b))

        # 2. Get AI Decision
        result = self.engine.think(prompt)

        # 3. CRITICAL FAIL-SAFE
        if not result:
            print(f"\n🚨 [CRITICAL ERROR] The AI Engine (Cloud & Backup) is unresponsive.")
            print(f"   🛑 Stopping Tournament to prevent corrupted rankings.")
            print(f"   💾 Check 'data/result/candidates_processed.parquet' for progress.")
            raise ConnectionError("Tournament Halted: THE Brain is DEAD. 💀")

        # 4. Normal Processing
        return result

    # ✅ NEW HELPER: Appends to the log list safely
    def _log_event(self, cand_id, message):
        """Finds the candidate by ID and appends a message to their battle log."""
        # Find index
        indices = self.df.index[self.df['id'] == cand_id].tolist()
        if not indices: return
        
        idx = indices[0]
        
        # Get current log (safely handle NaN or empty)
        current_log = self.df.at[idx, 'battle_log']
        if not isinstance(current_log, list):
            current_log = []
            
        # Append new message
        current_log.append(message)
        
        # Save back
        self.df.at[idx, 'battle_log'] = current_log

    # ✅ MODIFIED RUN_TOURNAMENT: Now with Logging
    def run_tournament(self, test_mode=False) -> list:
        print(f"🏟️  The Colosseum is Open. {len(self.df)} candidates entering...")
        
        # Ensure columns exist
        for col in ['evidence', 'meta_name']:
            if col not in self.df.columns: self.df[col] = None
            
        # Initialize battle_log as empty lists
        self.df['battle_log'] = [[] for _ in range(len(self.df))]
        
        self.df = self.df.sample(frac=1).reset_index(drop=True)

        with Progress() as progress:
            task = progress.add_task("[red]⚔️  Fighting...", total=len(self.df))
            
            for index, row in self.df.iterrows():
                cand_id = row['id']
                cand_name = row.get('meta_name')
                if not cand_name:
                    cand_name = cand_id[:6] # Fallback to ID (e.g., "8f2a1c")
                else:
                    cand_name = str(cand_name)[:10]
                
                # PHASE 1: FILL ARENA
                if len(self.arena) < 2:
                    self.arena.append(cand_id)
                    if len(self.arena) == 2:
                        id_a = self.arena[0]
                        id_b = self.arena[1]
                        
                        print(f"⚔️  First Blood: {id_a[:6]} vs {id_b[:6]}")
                        
                        winner_data = self._battle(id_a, id_b, mode="newcomer")
                        winner = winner_data.get('winner_id')
                        reason = winner_data.get('reason', 'No reason')
                        
                        if winner == id_b:
                            self.arena = [id_b, id_a]
                            loser = id_a
                        else:
                            loser = id_b

                        # ✅ LOGGING
                        self._log_event(winner, f"🏆 WON First Blood vs {loser[:6]}")
                        self._log_event(loser,  f"❌ LOST First Blood vs {winner[:6]}: {reason}")
                        
                        if test_mode:
                            print("🛑 TEST MODE: Stopping after first battle.")
                            return self.arena

                    progress.update(task, advance=1)
                    continue

                # PHASE 2: GATEKEEPER
                if len(self.arena) >= self.capacity:
                    gatekeeper_id = self.arena[-1]
                    print(f"🛡️  Gatekeeper Battle: {cand_name} vs Gatekeeper ({gatekeeper_id[:6]})")
                    
                    decision = self._battle(cand_id, gatekeeper_id, mode="gatekeeper")
                    winner = decision.get('winner_id')
                    reason = decision.get('reason', 'No reason provided.')
                    
                    if winner == gatekeeper_id:
                        print(f"   🚫 Rejected {cand_name}.")
                        # ✅ LOGGING
                        self._log_event(cand_id, f"❌ LOST to Gatekeeper: {reason}")
                        self._log_event(gatekeeper_id, f"🛡️ DEFENDED rank against Challenger {cand_id[:6]}")
                        
                        progress.update(task, advance=1)
                        continue 
                    else:
                        print(f"   ✅ Gatekeeper Defeated! Exiling {gatekeeper_id[:6]}.")
                        # ✅ LOGGING
                        self._log_event(cand_id, f"🏆 DEFEATED Gatekeeper {gatekeeper_id[:6]}")
                        self._log_event(gatekeeper_id, f"💀 KICKED OUT by Challenger {cand_id[:6]}: {reason}")
                        
                        self.arena.pop()

                # PHASE 3: RANKING
                self._binary_insert(cand_id)
                self._log_event(cand_id, f"📈 ENTERED Top {self.capacity} Arena")

                if index % 5 == 0: self.df.to_parquet(RESULT_DIR / "candidates_processed.parquet")
                progress.update(task, advance=1)
                
                time.sleep(2) 

        return self.arena

    def _binary_insert(self, candidate_id) -> None:
        print(f"   ⚖️  Ranking {candidate_id[:6]} in Arena...")
        low = 0
        high = len(self.arena) - 1
        while low <= high:
            mid = (low + high) // 2
            winner_data = self._battle(candidate_id, self.arena[mid], mode="ranker")
            winner = winner_data.get('winner_id')
            
            if winner == candidate_id: high = mid - 1
            else: low = mid + 1
            
        self.arena.insert(low, candidate_id)
        print(f"   🏅 Placed at Rank #{low + 1}")