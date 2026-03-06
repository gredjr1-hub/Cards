import streamlit as st
import random
import json
import re
import urllib.parse
import textwrap
import base64
import requests 
import time

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")

# --- Base64 URL Decoders ---
def get_url_jsonbin(): return base64.b64decode("aHR0cHM6Ly9hcGkuanNvbmJpbi5pby92My9iLw==").decode("utf-8")
def get_url_placeholder(): return base64.b64decode("aHR0cHM6Ly9wbGFjZWhvbGQuY28vMjU2eDM4NC8yYjJiMzYvODg4ODg4LnBuZz90ZXh0PQ==").decode("utf-8")
def get_url_hf(): return base64.b64decode("aHR0cHM6Ly9yb3V0ZXIuaHVnZ2luZ2ZhY2UuY28vaGYtaW5mZXJlbmNlL21vZGVscy9ibGFjay1mb3Jlc3QtbGFicy9GTFVYLjEtc2NobmVsbA==").decode("utf-8")

# --- Cloud Repository System ---
def load_repository():
    bin_id = st.secrets.get("JSONBIN_BIN_ID")
    api_key = st.secrets.get("JSONBIN_API_KEY")
    if not bin_id or not api_key: return {}
    try:
        url = f"{get_url_jsonbin()}{bin_id}/latest"
        headers = {"X-Master-Key": api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("record", {})
    except Exception as e:
        print(f"Cloud load error: {e}")
    return {}

def save_to_repository(card_name, image_data):
    bin_id = st.secrets.get("JSONBIN_BIN_ID")
    api_key = st.secrets.get("JSONBIN_API_KEY")
    if not bin_id or not api_key: return
    try:
        db = load_repository()
        db[card_name] = image_data 
        url = f"{get_url_jsonbin()}{bin_id}"
        headers = {"Content-Type": "application/json", "X-Master-Key": api_key}
        requests.put(url, json=db, headers=headers)
    except Exception as e:
        print(f"Cloud save error: {e}")

def sync_art_across_game(card_name, image_data):
    locations = [
        st.session_state.deck, st.session_state.hand, st.session_state.board,
        st.session_state.enemy_deck, st.session_state.enemy_hand, st.session_state.enemy_board
    ]
    for loc in locations:
        for c in loc:
            if c['name'] == card_name:
                c['image'] = image_data
                c['has_ai_art'] = True

# --- NEW: Automated Just-In-Time Rendering Engine ---
def ensure_card_art(card, theme):
    """Automatically fetches, saves, and syncs card art with a built-in retry for waking models."""
    if card.get('has_ai_art', False): return
    
    # Fast-check the database just in case it was painted in the background
    db = load_repository()
    if card['name'] in db:
        card['image'] = db[card['name']]
        card['has_ai_art'] = True
        return
        
    for attempt in range(2):
        new_img, error_msg = fetch_ai_image(card['name'], card.get('type', 'Attack'), theme)
        if new_img:
            card['image'] = new_img
            card['has_ai_art'] = True
            save_to_repository(card['name'], new_img)
            sync_art_across_game(card['name'], new_img)
            return
        elif "waking up" in error_msg and attempt == 0:
            time.sleep(5) # Give Hugging Face 5 seconds to wake up, then try once more
        else:
            break # Fails gracefully, leaves the placeholder intact

# --- Global CSS ---
st.markdown("""
<style>
/* Playmat & HUD Styling */
.playmat-container { background: radial-gradient(circle at center, #2a2d34 0%, #141518 100%); padding: 30px; border-radius: 12px; border: 2px solid #3a3f4a; box-shadow: inset 0 0 50px rgba(0,0,0,0.8); }
.board-divider { height: 4px; background: linear-gradient(90deg, transparent, #4a8cff, transparent); margin: 20px 0; opacity: 0.5; }
.empty-slot { width: 100%; max-width: 240px; aspect-ratio: 2.5/3.5; border: 3px dashed #444; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #555; font-weight: bold; background: rgba(0,0,0,0.3); margin: 0 auto; }
.hud-box { background: rgba(0,0,0,0.6); padding: 15px; border-radius: 8px; border: 1px solid #555; text-align: center; }

/* Card Animations & 3D Flip */
.flip-card { background-color: transparent; width: 100%; max-width: 240px; min-height: 336px; aspect-ratio: 2.5 / 3.5; perspective: 1000px; margin: 0 auto; }
.flip-card-inner { position: relative; width: 100%; height: 100%; text-align: center; transition: transform 0.6s ease-in-out, box-shadow 0.3s ease; transform-style: preserve-3d; -webkit-transform-style: preserve-3d; cursor: pointer; border-radius: 12px; }
.flip-checkbox:checked ~ .flip-card-inner { transform: rotateY(180deg); -webkit-transform: rotateY(180deg); }
.flip-card-inner:hover { transform: translateY(-8px) scale(1.03); }
.flip-checkbox:checked ~ .flip-card-inner:hover { transform: rotateY(180deg) translateY(-8px) scale(1.03); }
.is-selected .flip-card-inner { transform: translateY(-15px) scale(1.05); z-index: 10; box-shadow: 0 10px 30px rgba(74,140,255,0.8) !important; }

/* Faces */
.flip-card-front, .flip-card-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; -webkit-backface-visibility: hidden; border-radius: 12px; overflow: hidden; background: linear-gradient(135deg, #1e1e24, #101014); color: white; font-family: sans-serif; box-sizing: border-box; }
.flip-card-back { transform: rotateY(180deg); -webkit-transform: rotateY(180deg); background: rgba(15, 15, 20, 0.95); display: flex; flex-direction: column; }
.card-back-design { background: radial-gradient(circle, #2a3b5c, #101420); border: 4px solid #4a8cff; display: flex; align-items: center; justify-content: center; font-size: 40px; color: rgba(255,255,255,0.2); }

/* Rarity & States */
.rarity-Common .flip-card-inner { border: 3px solid #666666; }
.rarity-Rare .flip-card-inner { border: 3px solid #0070dd; box-shadow: 0 0 10px rgba(0,112,221,0.5); }
.rarity-Epic .flip-card-inner { border: 3px solid #a335ee; box-shadow: 0 0 15px rgba(163,53,238,0.6); }
.rarity-Legendary .flip-card-inner { border: 3px solid #ff8000; box-shadow: 0 0 20px rgba(255,128,0,0.8); }
.is-targetable .flip-card-inner { box-shadow: 0 0 0 4px rgba(255,50,50,0.8), 0 0 30px rgba(255,50,50,0.6); cursor: crosshair; animation: pulseTarget 1.5s infinite; }
.has-taunt .flip-card-inner { border-color: #eee !important; box-shadow: 0 0 0 4px #aaa, 0 0 15px #fff !important; }

/* Keyframes */
@keyframes pulseTarget { 0% { transform: scale(1); filter: brightness(1); } 50% { transform: scale(1.02); filter: brightness(1.3); } 100% { transform: scale(1); filter: brightness(1); } }
@keyframes lungeUp { 0% { transform: translateY(0); } 50% { transform: translateY(-40px) scale(1.1); z-index: 50;} 100% { transform: translateY(0); } }
@keyframes shakeDamage { 0% { transform: translateX(0); filter: brightness(1); } 20% { transform: translateX(-15px) rotate(-5deg); filter: brightness(2) hue-rotate(-50deg); } 40% { transform: translateX(15px) rotate(5deg); } 60% { transform: translateX(-15px) rotate(-5deg); } 80% { transform: translateX(15px) rotate(5deg); } 100% { transform: translateX(0); filter: brightness(1); } }
@keyframes pulseBuff { 0% { transform: scale(1); } 50% { transform: scale(1.1); filter: drop-shadow(0 0 20px #00ff00) brightness(1.5); } 100% { transform: scale(1); } }

.anim-attack .flip-card-inner { animation: lungeUp 0.5s ease; }
.anim-damage .flip-card-inner { animation: shakeDamage 0.5s ease; }
.anim-buff .flip-card-inner { animation: pulseBuff 0.6s ease; }

.stButton button { width: 100%; border-radius: 8px; font-weight: bold; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px;}
.ap-cost { background: #4a8cff; color: white; border-radius: 50%; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; position: absolute; top: -10px; left: -10px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); z-index: 20;}
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
state_defaults = {
    'game_active': False, 'game_over': False, 'winner': None,
    'theme': "", 'deck': [], 'hand': [], 'board': [],
    'enemy_deck': [], 'enemy_hand': [], 'enemy_board': [],
    'player_hp': 30, 'enemy_hp': 30,
    'max_ap': 3, 'current_ap': 3, 
    'active_stage': None, 'lore': "",
    'turn_count': 1, 'battle_log': [],
    'selected_attacker': None, 'selected_buff': None, 
    'attacks_used': set(), 'animation_state': {}
}
for k, v in state_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

def log_event(message: str):
    st.session_state.battle_log.insert(0, message)
    if len(st.session_state.battle_log) > 8: st.session_state.battle_log.pop()

def check_win_condition():
    if st.session_state.enemy_hp <= 0:
        st.session_state.game_over = True
        st.session_state.winner = "Player"
    elif st.session_state.player_hp <= 0:
        st.session_state.game_over = True
        st.session_state.winner = "Enemy"

def cleanup_dead_cards():
    st.session_state.board = [c for c in st.session_state.board if not c.get('is_dead', False)]
    st.session_state.enemy_board = [c for c in st.session_state.enemy_board if not c.get('is_dead', False)]
    st.session_state.hand = [c for c in st.session_state.hand if not c.get('is_consumed', False)]

# --- Live API Integration ---
def call_llm_api(theme):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key: return None

    system_prompt = f"""
    You are an expert card game designer like the creators of Hearthstone. Create a thematic scenario based on: '{theme}'.
    Return ONLY a valid JSON object matching this template:
    {{
      "lore": "Two paragraphs describing the conflict.",
      "stage": {{"name": "Stage Name", "type": "Stage"}},
      "player_cards": [
        {{ 
          "name": "Card Name", "type": "Attack", "rarity": "Rare", "atk": 5, "def": 4, 
          "desc": "Lore sentence.", 
          "mechanics": ["Taunt"], 
          "ability": {{"name": "Shield Wall", "desc": "Takes damage for others."}} 
        }},
        {{ "name": "Healing Spell", "type": "Buff", "rarity": "Common", "desc": "Lore sentence.", "stat_modifier": {{"atk": 1, "def": 2}} }}
      ],
      "enemy_cards": [ ... same structure as player_cards ... ]
    }}
    CRITICAL INSTRUCTIONS:
    1. Generate exactly 6 Attack cards and 2 Buff cards per faction.
    2. 'type' MUST be exactly "Attack" or "Buff".
    3. 'mechanics' MUST be an array. Include at least 2 cards per faction with mechanics like: "Taunt" (Must be attacked first), "Lifesteal", "Cleave", or "Deathrattle".
    """
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model='gemini-2.5-pro', contents=system_prompt)
        raw_text = getattr(response, 'text', None) or str(response)
        cleaned_text = re.sub(r'```json\n|\n```|```', '', raw_text).strip()
        return json.loads(cleaned_text)
    except Exception as e:
        st.error(f"Failed to generate scenario from AI. Error: {e}")
        return None

def fetch_placeholder_image(card_name: str) -> str:
    safe_name = urllib.parse.quote(card_name.replace(" ", "\n"))
    return f"{get_url_placeholder()}{safe_name}"

def fetch_ai_image(card_name: str, card_type: str, theme: str):
    hf_token = st.secrets.get("HF_TOKEN", "")
    if not hf_token: return None, "Missing HF_TOKEN in secrets.toml!"
    
    if card_type == "Buff":
        prompt_text = f"A fantasy trading card illustration of a magical item or spell '{card_name}'. Theme: {theme}. Masterpiece, highly detailed, dark background, single object focus."
    else:
        prompt_text = f"A fantasy trading card portrait of a character/creature '{card_name}'. Theme: {theme}. Masterpiece, highly detailed character concept art."
        
    try:
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {"inputs": prompt_text}
        response = requests.post(get_url_hf(), headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            b64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{b64}", None
        elif response.status_code == 503:
            return None, "Model is waking up"
        else:
            return None, f"HF API Error {response.status_code}"
    except Exception as e:
        return None, str(e) 

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario: return

    st.session_state.theme = theme
    st.session_state.lore = scenario.get("lore", "War has broken out.")
    db = load_repository()

    def process_deck(cards, is_player):
        deck = []
        for i, card in enumerate(cards * 3): 
            new_card = card.copy()
            new_card['id'] = f"{'p' if is_player else 'e'}_{i}_{random.randint(100,999)}"
            new_card['rarity'] = card.get('rarity', 'Common')
            new_card['desc'] = card.get('desc', 'A combatant enters the fray.')
            
            mechs = card.get('mechanics', [])
            new_card['mechanics'] = mechs if isinstance(mechs, list) else [str(mechs)] if mechs else []
            
            ab = card.get('ability', {})
            if not isinstance(ab, dict): new_card['ability'] = {'name': 'Ability', 'desc': str(ab) if ab else ''}
            else: new_card['ability'] = ab
                
            mods = card.get('stat_modifier', {})
            if not isinstance(mods, dict): new_card['stat_modifier'] = {'atk': 1, 'def': 1}
            else: new_card['stat_modifier'] = mods
            
            card_type = card.get('type', 'Attack')
            if card_type not in ['Attack', 'Buff']: card_type = 'Attack' if 'atk' in card else 'Buff'
            new_card['type'] = card_type
            
            new_card['ability_used'] = False
            new_card['is_dead'] = False
            new_card['is_consumed'] = False
            new_card['applied_buffs'] = [] 
            new_card['sick'] = True
            
            if new_card['name'] in db:
                new_card['image'] = db[new_card['name']]
                new_card['has_ai_art'] = True
            else:
                new_card['image'] = fetch_placeholder_image(new_card['name'])
                new_card['has_ai_art'] = False
            deck.append(new_card)
        random.shuffle(deck)
        return deck

    st.session_state.deck = process_deck(scenario.get("player_cards", []), True)
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(4)]
    st.session_state.enemy_deck = process_deck(scenario.get("enemy_cards", []), False)
    st.session_state.enemy_hand = [st.session_state.enemy_deck.pop() for _ in range(4)]
    
    st.session_state.player_hp = 30
    st.session_state.enemy_hp = 30
    st.session_state.max_ap = 3
    st.session_state.current_ap = 3
    st.session_state.turn_count = 1
    st.session_state.battle_log = ["The battle begins! You have 3 Action Points."]
    for k in ['selected_attacker', 'selected_buff', 'attacks_used', 'animation_state']:
        if k == 'attacks_used': st.session_state[k] = set()
        elif k == 'animation_state': st.session_state[k] = {}
        else: st.session_state[k] = None
        
    st.session_state.game_active = True
    st.session_state.game_over = False

    # AUTOMATION 1: JIT Render Starting Hand
    with st.spinner("Painting your starting hand..."):
        for card in st.session_state.hand:
            ensure_card_art(card, theme)

def play_card(card_id, is_player=True):
    if is_player and st.session_state.current_ap < 1: 
        st.warning("Not enough AP to deploy!"); return
        
    board = st.session_state.board if is_player else st.session_state.enemy_board
    if len(board) >= 5:
        st.warning("Board is full! Max 5 units."); return

    cleanup_dead_cards()
    hand = list(st.session_state.hand if is_player else st.session_state.enemy_hand)
    deck = list(st.session_state.deck if is_player else st.session_state.enemy_deck)
    board = list(st.session_state.board if is_player else st.session_state.enemy_board)
    
    card_idx = next((i for i, c in enumerate(hand) if c['id'] == card_id), None)
    if card_idx is None: return

    card = hand.pop(card_idx)
    card['sick'] = True
    board.append(card)
    
    # AUTOMATION 2: JIT Render Drawn Cards
    if deck: 
        drawn_card = deck.pop()
        if is_player and not drawn_card['has_ai_art']:
            with st.spinner(f"Drawing and Painting: {drawn_card['name']}..."):
                ensure_card_art(drawn_card, st.session_state.theme)
        hand.append(drawn_card)
    
    if is_player:
        st.session_state.hand = hand
        st.session_state.board = board
        st.session_state.deck = deck
        st.session_state.current_ap -= 1
    else:
        st.session_state.enemy_hand = hand
        st.session_state.enemy_board = board
        st.session_state.enemy_deck = deck
        
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} deployed {card['name']}.")

def apply_buff(buff_id, target_id):
    if st.session_state.current_ap < 1: return
    cleanup_dead_cards()
    buff_card = next((c for c in st.session_state.hand if c['id'] == buff_id), None)
    target_card = next((c for c in st.session_state.board if c['id'] == target_id), None)
    if not buff_card or not target_card: return
    
    st.session_state.current_ap -= 1
    mods = buff_card.get('stat_modifier', {})
    if not isinstance(mods, dict): mods = {'atk': 1, 'def': 1}
    
    atk_mod = mods.get('atk', 0)
    def_mod = mods.get('def', 0)
    target_card['atk'] = target_card.get('atk', 0) + atk_mod
    target_card['def'] = target_card.get('def', 0) + def_mod
    
    atk_str = f"+{atk_mod}" if atk_mod >= 0 else f"{atk_mod}"
    def_str = f"+{def_mod}" if def_mod >= 0 else f"{def_mod}"
    buff_label = f"{buff_card['name']} ({atk_str} ATK, {def_str} DEF)"
    
    if 'applied_buffs' not in target_card: target_card['applied_buffs'] = []
    target_card['applied_buffs'].append(buff_label)
    
    buff_card['is_consumed'] = True 
    log_event(f"✨ Applied {buff_card['name']} to {target_card['name']} ({atk_str} ATK, {def_str} DEF)!")
    st.session_state.animation_state = {'type': 'buff', 'target_id': target_card['id']}
    
    st.session_state.board = list(st.session_state.board)
    hand = list(st.session_state.hand)
    
    # AUTOMATION 2: JIT Render Drawn Cards (after buff cast)
    if st.session_state.deck: 
        drawn_card = st.session_state.deck.pop()
        if not drawn_card['has_ai_art']:
            with st.spinner(f"Drawing and Painting: {drawn_card['name']}..."):
                ensure_card_art(drawn_card, st.session_state.theme)
        hand.append(drawn_card)
    st.session_state.hand = hand

def trigger_ability(card_id):
    if st.session_state.current_ap < 1: return
    cleanup_dead_cards()
    card = next((c for c in st.session_state.board if c['id'] == card_id), None)
    if not card: return
    
    st.session_state.current_ap -= 1
    card['ability_used'] = True
    
    ab = card.get('ability', {})
    if not isinstance(ab, dict): ab = {'name': 'Ability', 'desc': str(ab)}
    ab_name = ab.get('name', 'Ability')
    
    st.session_state.enemy_hp -= 2
    log_event(f"⚡ {card['name']} cast {ab_name}! (2 DMG to Leader)")
    
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': card['id']}
    st.session_state.board = list(st.session_state.board)
    check_win_condition()

def has_taunt(board):
    return any("Taunt" in c.get('mechanics', []) for c in board if not c.get('is_dead'))

def resolve_attack(attacker_id, target_id):
    if st.session_state.current_ap < 1: return
    cleanup_dead_cards()
    attacker = next((c for c in st.session_state.board if c['id'] == attacker_id), None)
    target = next((c for c in st.session_state.enemy_board if c['id'] == target_id), None)
    if not attacker or not target: return

    if has_taunt(st.session_state.enemy_board) and "Taunt" not in target.get('mechanics', []):
        st.error("You MUST attack the enemy unit with Taunt first!"); return

    st.session_state.current_ap -= 1
    atk = int(attacker.get('atk', 0))
    target['def'] = int(target.get('def', 0)) - atk
    log_event(f"🎯 {attacker['name']} hit {target['name']} for {atk} DMG!")
    
    if "Lifesteal" in attacker.get('mechanics', []):
        st.session_state.player_hp += atk
        log_event(f"🩸 {attacker['name']}'s Lifesteal healed you for {atk}!")

    st.session_state.attacks_used.add(attacker.get('id'))
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id'], 'target_id': target['id']}

    if target['def'] <= 0:
        log_event(f"💀 {target['name']} was destroyed!")
        target['is_dead'] = True 
        st.session_state.enemy_board = [c for c in st.session_state.enemy_board if c['id'] != target['id']]
    else:
        st.session_state.enemy_board = list(st.session_state.enemy_board)
        
    check_win_condition()

def resolve_direct_attack(attacker_id):
    if st.session_state.current_ap < 1: return
    cleanup_dead_cards()
    attacker = next((c for c in st.session_state.board if c['id'] == attacker_id), None)
    if not attacker: return

    if has_taunt(st.session_state.enemy_board):
        st.error("A Taunt unit blocks your path to the leader!"); return

    st.session_state.current_ap -= 1
    atk = int(attacker.get('atk', 0))
    st.session_state.enemy_hp -= atk
    
    if "Lifesteal" in attacker.get('mechanics', []):
        st.session_state.player_hp += atk
        log_event(f"🩸 Lifesteal healed you for {atk}!")

    st.session_state.attacks_used.add(attacker.get('id'))
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id']}
    log_event(f"💥 {attacker['name']} hit the enemy leader for {atk} DMG!")
    check_win_condition()

def execute_enemy_turn():
    cleanup_dead_cards()
    log_event("--- Enemy Turn ---")
    st.session_state.animation_state = {} 
    
    for c in st.session_state.enemy_board: c['sick'] = False
    
    if st.session_state.enemy_hand and len(st.session_state.enemy_board) < 5:
        for c in st.session_state.enemy_hand:
            if c.get('type') == 'Attack':
                # AUTOMATION 3: JIT Render Enemy Played Cards
                if not c['has_ai_art']:
                    with st.spinner(f"Enemy deploying {c['name']}..."):
                        ensure_card_art(c, st.session_state.theme)
                play_card(c['id'], is_player=False)
                break

    for enemy_card in list(st.session_state.enemy_board):
        if enemy_card.get('type') == 'Attack' and not enemy_card.get('is_dead') and not enemy_card.get('sick', False):
            atk = int(enemy_card.get('atk', 0))
            valid_targets = [c for c in st.session_state.board if not c.get('is_dead')]
            
            taunts = [t for t in valid_targets if "Taunt" in t.get('mechanics', [])]
            target = random.choice(taunts) if taunts else (valid_targets[0] if valid_targets else None)
            
            if target:
                target['def'] = int(target.get('def', 0)) - atk
                log_event(f"⚔️ Enemy {enemy_card['name']} hit {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 Your {target['name']} was destroyed!")
                    target['is_dead'] = True
                    st.session_state.board = [c for c in st.session_state.board if c['id'] != target['id']]
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 Enemy {enemy_card['name']} hit YOU for {atk} DMG!")

    st.session_state.board = list(st.session_state.board)
    check_win_condition()
    st.session_state.turn_count += 1
    
    st.session_state.max_ap = min(10, 3 + (st.session_state.turn_count // 2))
    st.session_state.current_ap = st.session_state.max_ap
    
    for c in st.session_state.board: c['sick'] = False
    st.session_state.attacks_used = set()
    log_event(f"--- Your Turn (AP: {st.session_state.max_ap}) ---")

def end_turn():
    st.session_state.selected_attacker = None
    st.session_state.selected_buff = None
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_type, is_enemy=False, is_hidden=False):
    if is_hidden: 
        html = "<div class='flip-card'><div class='flip-card-inner'><div class='flip-card-front card-back-design'>🔮</div></div></div>"
        st.markdown(html, unsafe_allow_html=True)
        return

    card_key = f"{location_type}_{card['id']}"
    is_selected_attacker = (not is_enemy and location_type == 'board' and st.session_state.selected_attacker == card.get('id'))
    is_selected_buff = (not is_enemy and location_type == 'hand' and st.session_state.selected_buff == card.get('id'))
    
    enemy_taunt_active = has_taunt(st.session_state.enemy_board)
    is_valid_enemy_target = False
    if is_enemy and location_type == 'eboard' and st.session_state.selected_attacker and not card.get('is_dead'):
        if not enemy_taunt_active or "Taunt" in card.get('mechanics', []):
            is_valid_enemy_target = True

    is_targetable_friendly = (not is_enemy and location_type == 'board' and st.session_state.selected_buff is not None and not card.get('is_dead'))

    wrapper_classes = [f"rarity-{card.get('rarity', 'Common')}"]
    if "Taunt" in card.get('mechanics', []): wrapper_classes.append("has-taunt")
    if is_selected_attacker or is_selected_buff: wrapper_classes.append("is-selected")
    if is_valid_enemy_target or is_targetable_friendly: wrapper_classes.append("is-targetable")
    
    anim_state = st.session_state.get('animation_state', {})
    if anim_state.get('attacker_id') == card['id']: wrapper_classes.append("anim-attack")
    if anim_state.get('target_id') == card['id']: 
        wrapper_classes.append("anim-buff" if anim_state.get('type') == 'buff' else "anim-damage")

    ap_badge = "<div class='ap-cost'>1</div>" if location_type == 'hand' and not is_enemy else ""

    html = f"<div class='flip-card {' '.join(wrapper_classes)}'>"
    html += f"<label style='display:block; width:100%; height:100%; margin:0; cursor:pointer;' for='flip_{card_key}'>"
    html += f"<input type='checkbox' id='flip_{card_key}' class='flip-checkbox' style='display:none;'>"
    html += "<div class='flip-card-inner'>"
    
    # --- FRONT OF CARD ---
    html += "<div class='flip-card-front'>"
    html += ap_badge
    html += f"<img src='{card.get('image', '')}' style='width:100%; height:100%; object-fit:cover; opacity:0.9; background-color: #2b2b36;'>"
    
    html += "<div style='position:absolute; top:10px; width:100%; display:flex; justify-content:space-between; align-items:flex-start; padding:0 10px; font-weight:bold; font-size:16px; text-shadow:2px 2px 4px #000; z-index: 5;'>"
    
    if card.get('type') == 'Attack':
        buff_indicator = " ✨" if card.get('applied_buffs') else ""
        sick_indicator = " 💤" if card.get('sick', False) else ""
        html += f"<span style='background:rgba(200,40,40,0.9); padding:2px 8px; border-radius:4px;'>⚔️ {card.get('atk', 0)}{sick_indicator}</span>"
    else:
        html += "<span style='width:40px;'></span>" 
        
    html += f"<span style='background:rgba(0,0,0,0.8); padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold; text-transform:uppercase; letter-spacing:1px; border:1px solid #555; text-shadow:none; margin-top:2px;'>{card.get('type', 'Unknown')}</span>"
    
    if card.get('type') == 'Attack':
        html += f"<span style='background:rgba(40,100,200,0.9); padding:2px 8px; border-radius:4px;'>🛡️ {card.get('def', 0)}{buff_indicator}</span>"
    else:
        html += "<span style='width:40px;'></span>"

    html += "</div>"
    
    html += "<div style='position:absolute; bottom:0; width:100%; background:rgba(0,0,0,0.85); padding:8px; border-top:1px solid #555; z-index: 5;'>"
    html += f"<h4 style='margin:0; font-size:14px; text-overflow: ellipsis; white-space: nowrap; overflow:hidden;'>{card['name']}</h4>"
    html += "</div></div>"

    # --- BACK OF CARD ---
    html += "<div class='flip-card-back'>"
    html += "<div style='padding:15px; flex-grow:1; overflow-y:auto;'>"
    html += f"<h4 style='margin:0 0 5px 0; border-bottom:1px solid #555; padding-bottom:5px; font-size:16px;'>{card['name']}</h4>"
    if card.get('mechanics'):
        html += f"<div style='font-size:11px; font-weight:bold; color:#ffeb3b; margin-bottom:5px;'>Keywords: {', '.join(card['mechanics'])}</div>"
    html += f"<p style='margin:0; font-size:12px; font-style:italic; color:#ddd;'>\"{card.get('desc', '')}\"</p>"
    if card.get('applied_buffs'):
        html += f"<div style='margin-top: 10px; font-size: 11px; color: #4a8cff; background:rgba(74,140,255,0.1); padding: 5px; border-radius: 4px;'><b>✨ Buffs:</b><br>{'<br>'.join(card['applied_buffs'])}</div>"
    html += "</div>"
    
    if 'ability' in card:
        ab = card['ability']
        if not isinstance(ab, dict): ab = {'name': 'Ability', 'desc': str(ab)}
        html += f"<div style='margin:0 10px 10px 10px; background:rgba(255,255,255,0.1); padding:8px; border-radius:6px; font-size:11px;'><b style='color:#ffeb3b;'>⚡ {ab.get('name','Ability')}</b><br>{ab.get('desc','')}</div>"
    
    if card.get('type') == 'Attack':
        html += f"<div style='padding:10px; display:flex; justify-content:space-between; font-weight:bold; font-size:16px; border-top:1px solid #555; background:rgba(0,0,0,0.4); margin-top:auto;'><span>⚔️ {card.get('atk', 0)}</span><span>🛡️ {card.get('def', 0)}</span></div>"
    elif card.get('type') == 'Buff':
        mods = card.get('stat_modifier', {})
        if not isinstance(mods, dict): mods = {'atk': 1, 'def': 1}
        html += f"<div style='padding:10px; font-weight:bold; font-size:14px; border-top:1px solid #555; background:rgba(0,0,0,0.4); text-align:center; margin-top:auto;'>Buff: +{mods.get('atk',0)} ATK / +{mods.get('def',0)} DEF</div>"

    html += "</div></div></label></div>"
    st.markdown(html, unsafe_allow_html=True)

    # --- Interaction Buttons ---
    is_disabled = card.get('is_dead', False) or card.get('is_consumed', False)
    has_ap = st.session_state.current_ap > 0
    
    if not is_disabled:
        if not is_enemy and location_type == 'hand':
            if card.get('type') == 'Attack':
                if st.button("Summon (1 AP)", key=f"play_{card_key}", type="primary", disabled=not has_ap):
                    play_card(card['id'], is_player=True); st.rerun()
            elif card.get('type') == 'Buff':
                if is_selected_buff:
                    if st.button("Cancel", key=f"cancel_{card_key}"):
                        st.session_state.selected_buff = None; st.rerun()
                else:
                    if st.button("Cast Spell (1 AP)", key=f"use_{card_key}", type="primary", disabled=not has_ap):
                        st.session_state.selected_buff = card['id']
                        st.session_state.selected_attacker = None; st.rerun()
                
                if is_selected_buff:
                    st.info("⬆️ Select board target")

        elif not is_enemy and location_type == 'board':
            if is_targetable_friendly:
                if st.button("Apply Here", key=f"apply_{card_key}", type="primary"):
                    apply_buff(st.session_state.selected_buff, card['id'])
                    st.session_state.selected_buff = None; st.rerun()
            elif card.get('type') == 'Attack':
                can_attack = card.get('id') not in st.session_state.attacks_used and not card.get('sick', False) and has_ap
                if is_selected_attacker:
                    if st.button("Cancel", key=f"cancel_atk_{card_key}"):
                        st.session_state.selected_attacker = None; st.rerun()
                else:
                    btn_text = "💤 Sick" if card.get('sick') else "⚔️ Attack (1 AP)"
                    if st.button(btn_text, key=f"atk_{card_key}", type="primary", disabled=not can_attack):
                        st.session_state.selected_attacker = card['id']; st.rerun()
                
                if 'ability' in card and not card.get('ability_used', False):
                    if st.button("⚡ Ability (1 AP)", key=f"ab_{card_key}", disabled=not has_ap):
                        trigger_ability(card['id']); st.rerun()

        elif is_enemy and location_type == 'eboard' and st.session_state.selected_attacker and is_valid_enemy_target:
            if st.button("🎯 Strike", key=f"tgt_{card_key}", type="primary"):
                resolve_attack(st.session_state.selected_attacker, card['id'])
                st.session_state.selected_attacker = None; st.rerun()

def render_empty_slot():
    st.markdown("<div class='empty-slot'>Empty Slot</div>", unsafe_allow_html=True)

# --- Main UI Rendering ---
if not st.session_state.game_active:
    st.title("🃏 AI Lore Battler")
    st.markdown("Enter a theme to generate a deck. The AI will weave keywords like **Taunt** and **Lifesteal** into the cards.")
    theme_input = st.text_input("Theme (e.g., 'Old School RuneScape', 'Cyberpunk'):")
    if st.button("Start Battle", type="primary"):
        if theme_input:
            with st.spinner("Forging rules, keywords, and cards..."): setup_game(theme_input)
            st.rerun()

elif st.session_state.game_over:
    if st.session_state.winner == "Player": st.balloons(); st.success("# 🏆 VICTORY!")
    else: st.snow(); st.error("# 💀 DEFEAT...")
    if st.button("Main Menu", type="primary"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()

else:
    # --- ENEMY HUD ---
    col1, col2, col3 = st.columns([2, 6, 2])
    with col1: st.markdown(f"<div class='hud-box'><h3 style='color:#ff4a4a; margin:0;'>Enemy Leader</h3><h2>❤️ {st.session_state.enemy_hp}</h2></div>", unsafe_allow_html=True)
    with col2:
        if st.session_state.enemy_hand:
            ehand_cols = st.columns(len(st.session_state.enemy_hand))
            for i, card in enumerate(st.session_state.enemy_hand):
                with ehand_cols[i]: render_card(card, "ehand", is_enemy=True, is_hidden=True)
    with col3: st.markdown(f"<div class='hud-box' style='font-size:12px;'><br><b>Cards in Deck:</b> {len(st.session_state.enemy_deck)}<br><b>Cards in Hand:</b> {len(st.session_state.enemy_hand)}</div>", unsafe_allow_html=True)

    # --- THE PLAYMAT ---
    st.markdown("<div class='playmat-container'>", unsafe_allow_html=True)
    
    ecols = st.columns([1, 8, 1])
    with ecols[1]:
        slots = st.columns(5)
        for i in range(5):
            with slots[i]:
                if i < len(st.session_state.enemy_board): render_card(st.session_state.enemy_board[i], "eboard", is_enemy=True)
                else: render_empty_slot()

    status_text = "🟢 Awaiting Orders"
    if st.session_state.selected_attacker: 
        if has_taunt(st.session_state.enemy_board): status_text = "🛡️ You MUST attack a Taunt minion!"
        else: status_text = "🎯 Select an enemy target."
    elif st.session_state.selected_buff: status_text = "✨ Select a friendly card to buff."
    
    st.markdown("<div class='board-divider'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center; font-weight:bold; color:#aaa; margin-bottom:10px;'>{status_text}</div>", unsafe_allow_html=True)

    pcols = st.columns([1, 8, 1])
    with pcols[1]:
        slots = st.columns(5)
        for i in range(5):
            with slots[i]:
                if i < len(st.session_state.board): render_card(st.session_state.board[i], "board", is_enemy=False)
                else: render_empty_slot()
                
    st.markdown("</div><br>", unsafe_allow_html=True)

    # --- PLAYER HUD & HAND ---
    col1, col2, col3 = st.columns([2, 6, 2])
    with col1: 
        ap_color = "#4a8cff" if st.session_state.current_ap > 0 else "#ff4a4a"
        st.markdown(f"<div class='hud-box'><h3 style='color:#4a8cff; margin:0;'>Your Leader</h3><h2>❤️ {st.session_state.player_hp}</h2><h4 style='color:{ap_color};'>⚡ AP: {st.session_state.current_ap} / {st.session_state.max_ap}</h4></div>", unsafe_allow_html=True)
    
    with col2:
        if st.session_state.hand:
            hand_cols = st.columns(len(st.session_state.hand))
            for i, card in enumerate(st.session_state.hand):
                with hand_cols[i]: render_card(card, "hand", is_enemy=False)

    with col3:
        if st.button("⏭️ END TURN", use_container_width=True, type="primary"): end_turn(); st.rerun()
        
        if st.session_state.selected_attacker:
            if not has_taunt(st.session_state.enemy_board):
                if st.button("🎯 Attack Enemy Leader", key="tgt_enemy", type="primary", use_container_width=True):
                    resolve_direct_attack(st.session_state.selected_attacker)
                    st.session_state.selected_attacker = None; st.rerun()
            else:
                st.error("Taunt blocks Leader!")
                
        with st.expander("📜 Battle Log", expanded=False):
            for log in st.session_state.battle_log: 
                st.markdown(f"<div style='font-size:12px; margin-bottom:4px; padding:4px; background:rgba(255,255,255,0.05); border-left: 2px solid #666;'>{log}</div>", unsafe_allow_html=True)
                
    st.write("---")
    if st.button("Surrender & Restart"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()