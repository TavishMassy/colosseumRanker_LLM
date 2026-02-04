import os
import random
import json
import string
from pathlib import Path

# --- CONFIG ---
RAW_DATA_DIR = Path("data/resumes")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

REAL_PORTFOLIOS = [
    {"url": "https://brittanychiang.com/", "owner": "Brittany Chiang"},
    {"url": "https://bruno-simon.com/", "owner": "Bruno Simon"},
    {"url": "https://matthewfarley.ca/", "owner": "Matt Farley"},
    {"url": "https://tamalsen.dev/", "owner": "Tamal Sen"},
    {"url": "https://www.jenniferdewalt.com/", "owner": "Jennifer Dewalt"},
    {"url": "https://leerob.io/", "owner": "Lee Robinson"},
    {"url": "https://overreacted.io/", "owner": "Dan Abramov"}
]

# Helper to generate unique fake contact data
def get_random_contact(name):
    domain = random.choice(["gmail.com", "outlook.com", "protonmail.com", "dev-hub.io"])
    clean_name = name.lower().replace(" ", ".")
    email = f"{clean_name}{random.randint(10, 99)}@{domain}"
    phone = f"+{random.randint(1, 99)}-{random.randint(700, 999)}-{random.randint(1000, 9999)}"
    return email, phone

def generate_sophisticated_chaos():
    resumes = []

    # 1. THE WRONG JOB (GORDON R.)
    name = "Gordon Ramsay-ish"
    email, phone = get_random_contact(name)
    resumes.append({
        "type": "WrongJob", "name": "Gordon_R_Chef",
        "content": f"NAME: {name}\nEMAIL: {email}\nPHONE: {phone}\nROLE: Executive Chef\nEXP: 20+ years\nLINK: https://www.gordonramsay.com/\nNOTE: Applying for Lead Developer."
    })

    # 2. THE TERRIBLE CANDIDATES (5 Lazy Larrys)
    for i in range(5):
        name = f"Lazy Larry {i}"
        email, phone = get_random_contact(name)
        resumes.append({
            "type": "Terrible", "name": f"Lazy_Larry_{i}",
            "content": f"Hi, I am {name}. Email: {email}. Phone: {phone}. I know computers. LINK: http://google.com"
        })

    # 3. THE OVER-FITS (5 Buzzword Bots)
    for i in range(5):
        name = f"Bot Architecture {i}"
        email, phone = get_random_contact(name)
        resumes.append({
            "type": "OverFit", "name": f"Buzzword_Bot_{i}",
            "content": f"SYNERGISTIC ARCHITECT: {name}\nCONTACT: {email} | {phone}\nSKILLS: Python, Java, Rust, Go, C++, Kubernetes, Docker, AWS, AI, Web3.\nLINK: https://zapier.com/blog/case-study-examples/"
        })

    # 4. THE ORIGINAL STRONG CANDIDATES (10 Professionals)
    names = ["Sarah Chen", "Elena Rodriguez", "Kenji Tanaka", "Liam Smith", "Priya Das", "Zaid Khan", "Chloe Muller", "Amit Sharma", "Sofia Rossi", "Lucas Meyer"]
    for i, name in enumerate(names):
        portfolio = random.choice(REAL_PORTFOLIOS)
        email, phone = get_random_contact(name)
        is_lie = random.random() > 0.5
        claimed_owner = name if not is_lie else "Jan Baszczok"
        
        resumes.append({
            "type": "Strong", "name": name.replace(" ", "_"),
            "content": f"NAME: {name}\nEMAIL: {email}\nPHONE: {phone}\nEXP: {random.randint(6, 12)} Yrs\nPORTFOLIO: {portfolio['url']}\nOWNER: {claimed_owner}"
        })

    # 5. THE NEW BATCH (30 Randomized Professionals)
    # These increase volume to test the Re-Ranker and Colosseum endurance
    more_names = [
        "Aarav Patel", "Mei Lin", "Hans Schmidt", "Sasha Ivanova", "Diego Garcia", 
        "Fatima Zahra", "Yuki Sato", "Lars Jensen", "Marie Curie-ish", "Isaac Newton-ish",
        "Grace Hopper-ish", "Ada Lovelace-ish", "Alan Turing-ish", "Nikola Tesla-ish", "Steve Jobs-ish",
        "Bill Gates-ish", "Mark Zuckerberg-ish", "Jeff Bezos-ish", "Elon Musk-ish", "Linus Torvalds-ish",
        "Guido van Rossum-ish", "James Gosling-ish", "Bjarne Stroustrup-ish", "Tim Berners-Lee-ish", "Vint Cerf-ish",
        "Brendan Eich-ish", "John Resig-ish", "Dan Abramov-ish", "Rich Harris-ish", "Evan You-ish"
    ]

    for i, name in enumerate(more_names):
        portfolio = random.choice(REAL_PORTFOLIOS)
        email, phone = get_random_contact(name)
        # Randomly assign quality to these 30: 20 Strong, 10 Overfit
        r_type = "Strong" if i < 20 else "OverFit"
        
        resumes.append({
            "type": f"MassTest_{r_type}", "name": name.replace(" ", "_"),
            "content": f"NAME: {name}\nEMAIL: {email}\nPHONE: {phone}\nROLE: Software Engineer\nLINK: {portfolio['url']}\nEXP: {random.randint(2, 15)} Yrs"
        })

    return resumes

def run():
    all_data = generate_sophisticated_chaos()
    print(f"🚀 Deploying {len(all_data)} Chaos Resumes to {RAW_DATA_DIR}...")
    
    for i, entry in enumerate(all_data):
        filename = RAW_DATA_DIR / f"{entry['type']}_{i:03d}_{entry['name']}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(entry['content'])
            
    print(f"✅ Created {len(all_data)} sophisticated test files.")
    print("🚦 Ready for Option 1 (Extractor) and Option 4 (Colosseum Battle).")

if __name__ == "__main__":
    run()