import os
import time
import json
import random
import requests
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from rich.progress import Progress

# --- CONFIGURATION ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "meta-llama/llama-3.3-70b-instruct:free"
DATA_DIR = Path("data")
PROMPTS_DIR = DATA_DIR / "prompts"
RESULT_DIR = DATA_DIR / "result"

class FactChecker:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def verify_link(self, url):
        """
        Visits a URL.
        Philosophy: If provided, it MUST work. Private/Dead = Lack of Detail.
        """
        # We still skip LinkedIn because it requires login (not candidate's fault)
        if "linkedin.com" in url:
             return {"status": "skipped_social", "content": "Social Profile (Not Scraped)"}
        
        try:
            # Random delay to be polite
            time.sleep(random.uniform(0.5, 1.5))
            
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                # Success! Proof of Work exists.
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "No Title"
                body_text = soup.get_text(separator=' ', strip=True)[:500]
                
                return {
                    "status": "verified_live",
                    "content": f"[Title: {title}] Content: {body_text}..."
                }
            
            # THE PENALTY ZONE
            # Any failure here is marked as "Lack of Detail" on the candidate's part.
            elif response.status_code == 404:
                return {"status": "flag_lack_of_detail", "content": "Link is Dead (404). Candidate failed to update resume."}
            
            elif response.status_code == 403:
                return {"status": "flag_lack_of_detail", "content": "Link is Private (403). Candidate failed to grant access."}
            
            else:
                return {"status": "flag_lack_of_detail", "content": f"Link Broken (Status {response.status_code})."}

        except Exception as e:
            # DNS errors, Connection Refused, etc.
            return {"status": "flag_lack_of_detail", "content": f"Link Unreachable. {str(e)}"}

class Colosseum:
    def __init__(self, candidates_df, battle_sheet):
        self.df = candidates_df
        self.sheet = battle_sheet
        self.investigator = FactChecker()
        self.arena = [] # Stores IDs of the Top 10 [Rank 1, Rank 2, ... Rank 10]
        self.capacity = 10
        
        # Load Prompts
        self.prompts = {
            "newcomer": self._load_prompt("judge_newcomer.txt"),
            "gatekeeper": self._load_prompt("judge_gatekeeper.txt"),
            "ranker": self._load_prompt("judge_ranker.txt")
        }

    def _load_prompt(self, filename):
        path = PROMPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"❌ Missing Prompt: {path}")
        with open(path, 'r') as f:
            return f.read()

    def _call_llm(self, prompt_text):
        """Standardized OpenRouter API Call"""
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8000", 
                    "X-Title": "Freelancer_Arbiter", 
                },
                data=json.dumps({
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt_text}],
                    "temperature": 0.2, # Low temp for strict JSON
                    "response_format": {"type": "json_object"} # Force JSON
                })
            )
            response.raise_for_status()
            return json.loads(response.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(f"   ⚠️ LLM Error: {e}")
            return None

    def _ensure_evidence(self, candidate_id):
        """JIT: Checks if row has evidence. If not, scrapes & saves."""
        idx = self.df.index[self.df['id'] == candidate_id].tolist()[0]
        
        # Check cache (assuming 'evidence' column exists and is not None)
        current_evidence = self.df.at[idx, 'evidence']
        if current_evidence is not None and len(str(current_evidence)) > 5:
            return # Already cached
        
        # Not cached? Scrape!
        print(f"   🛡️ JIT Scraping for {candidate_id[:8]}...")
        links = self.df.at[idx, 'contact_info'].get('links', [])
        evidence_list = []
        for link in links[:2]: # Max 2 links
            res = self.investigator.verify_link(link)
            if res: evidence_list.append({link: res})
            
        # Write-Back to DataFrame (Persistence)
        self.df.at[idx, 'evidence'] = json.dumps(evidence_list)

    def _get_dossier(self, candidate_id):
        """Prepares text for the prompt."""
        self._ensure_evidence(candidate_id) # Trigger JIT
        row = self.df.loc[self.df['id'] == candidate_id].iloc[0]
        return f"""
        ID: {row['id']}
        RESUME SUMMARY: {row['safe_text'][:2500]}
        EVIDENCE: {row['evidence']}
        """

    def _battle(self, id_a, id_b, mode="ranker"):
        """Runs a fight between A and B."""
        # 1. Select Template
        template = self.prompts[mode]
        
        # 2. Prepare Dossiers
        dossier_a = self._get_dossier(id_a)
        dossier_b = self._get_dossier(id_b)
        
        # 3. Fill Template
        filled_prompt = template.replace("{{role}}", self.sheet['role']) \
                                .replace("{{must_haves}}", str(self.sheet['must_haves'])) \
                                .replace("{{deal_breakers}}", str(self.sheet.get('deal_breakers', 'None'))) \
                                .replace("{{id_a}}", id_a) \
                                .replace("{{text_a}}", dossier_a) \
                                .replace("{{id_b}}", id_b) \
                                .replace("{{text_b}}", dossier_b)

        # 4. Call AI
        result = self._call_llm(filled_prompt)
        
        if not result:
            return id_a # Default to Challenger if AI fails (Fail-safe)

        # 5. Extraction Logic (Only for 'newcomer')
        if mode == "newcomer":
            # Save extracted metadata to DF
            for key in ['candidate_a_details', 'candidate_b_details']:
                if key in result:
                    details = result[key]
                    # Find which ID this belongs to
                    target_id = id_a if key == 'candidate_a_details' else id_b
                    idx = self.df.index[self.df['id'] == target_id][0]
                    self.df.at[idx, 'meta_name'] = details.get('name')
                    self.df.at[idx, 'meta_yoe'] = details.get('yoe')
                    self.df.at[idx, 'meta_role'] = details.get('current_role')

        # 6. Log the Loss (Save to Loser)
        winner = result.get('winner_id')
        loser = id_a if winner == id_b else id_b
        reason = result.get('reason', 'AI decision')
        
        l_idx = self.df.index[self.df['id'] == loser][0]
        self.df.at[l_idx, 'battle_log'] = f"Lost to {winner}. Reason: {reason}"
        
        return winner

    def run_tournament(self):
        # --- 1. SETUP (Run ONCE before the loop) ---
        print(f"🏟️  The Colosseum is Open. {len(self.df)} candidates entering...")
        
        # Initialize columns if missing
        for col in ['evidence', 'battle_log', 'meta_name', 'meta_yoe', 'meta_role']:
            if col not in self.df.columns: self.df[col] = None

        # Shuffle ONCE to prevent Order Bias
        self.df = self.df.sample(frac=1).reset_index(drop=True)

        # --- 2. THE TOURNAMENT LOOP ---
        with Progress() as progress:
            task = progress.add_task("[red]⚔️  Fighting in the Colosseum...", total=len(self.df))
            
            for index, row in self.df.iterrows():
                cand_id = row['id']
                
                # --- PHASE 1: FILL THE ARENA ---
                if len(self.arena) < 2:
                    self.arena.append(cand_id)
                    if len(self.arena) == 2:
                        # Initial Sort of first 2
                        print("⚔️  First Blood: Initializing Arena...")
                        winner = self._battle(self.arena[0], self.arena[1], mode="newcomer")
                        if winner == self.arena[1]:
                            self.arena = [self.arena[1], self.arena[0]]
                    
                    # Update progress for these early setup candidates
                    progress.update(task, advance=1)
                    continue

                # --- PHASE 2: INSERTION ---
                # 1. Gatekeeper Check (if full)
                if len(self.arena) >= self.capacity:
                    gatekeeper_id = self.arena[-1]
                    print(f"🛡️  Gatekeeper Battle: {cand_id[:6]} vs {gatekeeper_id[:6]}")
                    winner = self._battle(cand_id, gatekeeper_id, mode="gatekeeper")
                    
                    if winner == gatekeeper_id:
                        print(f"   🚫 Rejected.")
                        # CRITICAL: Update progress even if they are rejected!
                        progress.update(task, advance=1)
                        continue # Next candidate
                    else:
                        print(f"   ✅ Gatekeeper Defeated! Exiling {gatekeeper_id[:6]}.")
                        self.arena.pop() # Remove old #10

                # 2. Binary Search Insertion
                self._binary_insert(cand_id)
                
                # 3. Persistent Save (Every 5 candidates, save progress)
                if index % 5 == 0:
                    self.df.to_parquet(RESULT_DIR / "candidates_processed.parquet")
                
                # 4. Standard Update
                progress.update(task, advance=1)

        return self.arena

    def _binary_insert(self, candidate_id):
        """Finds exact rank using Binary Search battles."""
        print(f"   ⚖️  Ranking {candidate_id[:6]} in Arena...")
        low = 0
        high = len(self.arena) - 1
        
        while low <= high:
            mid = (low + high) // 2
            opponent_id = self.arena[mid]
            
            # Mode is 'newcomer' if we lack metadata, else 'ranker'
            # Simplified: always use 'ranker' for internal sorts to save tokens
            winner = self._battle(candidate_id, opponent_id, mode="ranker")
            
            if winner == candidate_id:
                # Better than Mid -> Go to Top half (Lower Index)
                high = mid - 1
            else:
                # Worse than Mid -> Go to Bottom half
                low = mid + 1
        
        self.arena.insert(low, candidate_id)
        print(f"   🏅 Placed at Rank #{low + 1}")