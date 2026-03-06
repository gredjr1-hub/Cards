import streamlit as st
import random
import json
import re
import urllib.parse
import textwrap
import base64
import requests 

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")

# --- Cloud Repository System (JSONBin) ---
def load_repository():
    bin_id = st.secrets.get("JSONBIN_BIN_ID")
    api_key = st.secrets.get("JSONBIN_API_KEY")
    if not bin_id or not api_key: return {}
    try:
        url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
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
        url = f"https://api.jsonbin.io/v3/b/{bin_id}"
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

# --- Global CSS ---
st.markdown("""
<style>
.flip-card { background-color: transparent; width: 100%; max-width: 240px; min-height: 336px; aspect-ratio: 2.5 / 3.5; perspective: 1000px; margin: 0 auto; }
.flip-card-inner { position: relative; width: 100%; height: 100%; text-align: center; transition: transform 0.6s ease-in-out, box-shadow 0.3s ease; transform-style: preserve-3d; -webkit-transform-style: preserve-3d; cursor: pointer; border-radius: 12px; }
.flip-checkbox:checked ~ .flip-card-inner { transform: rotateY(180deg); -webkit-transform: rotateY(180deg); }
.flip-card-inner:hover { transform: translateY(-4px) scale(1.02); }
.flip-checkbox:checked ~ .flip-card-inner:hover { transform: rotateY(180deg) translateY(-4px) scale(1.02); }
.is-selected .flip-card-inner { transform: translateY(-10px) scale(1.03); z-index: 10; }
.flip-card-front, .flip-card-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; -webkit-backface-visibility: hidden; border-radius: 12px; overflow: hidden; background: linear-gradient(135deg, #1e1e24, #101014); color: white; font-family: sans-serif; box-sizing: border-box; }
.flip-card-back { transform: rotateY(180deg); -webkit-transform: rotateY(180deg); background: rgba(15, 15, 20, 0.95); display: flex; flex-direction: column; }
.rarity-Common .flip-card-inner { border: 3px solid #666666; }
.rarity-Rare .flip-card-inner { border: 3px solid #0070dd; box-shadow: 0 0 10px rgba(0,112,221,0.5); }
.rarity-Epic .flip-card-inner { border: 3px solid #a335ee; box-shadow: 0 0 15px rgba(163,53,238,0.6); }
.rarity-Legendary .flip-card-inner { border: 3px solid #ff8000; box-shadow: 0 0 20px rgba(255,128,0,0.8); }
.is-targetable .flip-card-inner { box-shadow: 0 0 0 4px rgba(255,205,0,0.5), 0 0 20px rgba(255,205,0,0.6); cursor: crosshair; }
.is-selected .flip-card-inner { box-shadow: 0 0 0 4px rgba(74,140,255,0.5), 0 0 20px rgba(74,140,255,0.6); }
@keyframes lungeUp { 0% { transform: translateY(0); } 50% { transform: translateY(-30px) scale(1.05); } 100% { transform: translateY(0); } }
@keyframes shakeDamage { 0% { transform: translateX(0); filter: brightness(1); } 20% { transform: translateX(-10px); filter: brightness(2) hue-rotate(-50deg); } 40% { transform: translateX(10px); } 60% { transform: translateX(-10px); } 80% { transform: translateX(10px); } 100% { transform: translateX(0); filter: brightness(1); } }
@keyframes fadeOutDown { 0% { opacity: 1; transform: translateY(0) scale(1); filter: grayscale(0%); } 100% { opacity: 0; transform: translateY(30px) scale(0.9); filter: grayscale(100%); } }
@keyframes fadeOutUp { 0% { opacity: 1; transform: translateY(0) scale(1); filter: brightness(1); } 50% { filter: brightness(2); } 100% { opacity: 0; transform: translateY(-30px) scale(1.1); filter: brightness(0); } }
.anim-attack .flip-card-inner { animation: lungeUp 0.4s ease forwards; }
.anim-damage .flip-card-inner { animation: shakeDamage 0.4s ease forwards; }
.anim-death { animation: fadeOutDown 0.6s ease forwards; pointer-events: none; }
.anim-consume { animation: fadeOutUp 0.6s ease forwards; pointer-events: none; }
.stButton button { width: 100%; border-radius: 8px; font-weight: bold; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
state_defaults = {
    'game_active': False, 'game_over': False, 'winner': None,
    'theme': "", 'deck': [], 'hand': [], 'board': [],
    'enemy_deck': [], 'enemy_hand': [], 'enemy_board': [],
    'player_hp': 30, 'enemy_hp': 30,
    'active_stage': None, 'lore': "",
    'turn_count': 1, 'battle_log': [],
    'selected_attacker': None, 'selected_buff': None, 
    'attacks_used': set(), 'animation_state': {}
}
for k, v in state_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

def log_event(message: str):
    st.session_state.battle_log.insert(0, message)
    if len(st.session_state.battle_log) > 6: st.session_state.battle_log.pop()

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
    You are an expert card game designer. Create a balanced, thematic card game scenario based ONLY on this theme: '{theme}'.
    Return ONLY a valid JSON object matching this EXACT template:
    {{
      "lore": "Two paragraphs describing the conflict and factions.",
      "stage": {{"name": "Stage Name", "type": "Stage", "visuals": {{"css_gradient": "linear-gradient(to bottom, #111111, #444444)"}}}},
      "player_cards": [
        {{ "name": "Card Name", "type": "Attack", "rarity": "Rare", "atk": 5, "def": 4, "desc": "Lore sentence.", "ability": {{"name": "Strike", "desc": "Deals 2 damage."}} }},
        {{ "name": "Another Card", "type": "Buff", "rarity": "Common", "desc": "Lore sentence.", "stat_modifier": {{"atk": 2, "def": 0}} }}
      ],
      "enemy_cards": [ ... same structure as player_cards ... ]
    }}
    CRITICAL: Generate exactly 6 Attack cards and 2 Buff cards per faction.
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
    return f"[https://placehold.co/256x384/2b2b36/888888.png?text=](https://placehold.co/256x384/2b2b36/888888.png?text=){safe_name}"

def fetch_ai_image(card_name: str, card_type: str, theme: str, api_key: str):
    """Lazy Loader that returns a tuple: (image_data, error_message)."""
    if not api_key: return None, "Missing Gemini API Key."
    
    if card_type == "Buff":
        prompt_text = f"A harmless fantasy game prop representing '{card_name}'. Theme: {theme}. Single object focus, fantasy trading card illustration, masterpiece, dark background. No real weapons, completely safe for work."
    else:
        prompt_text = f"A stylized, harmless fictional character avatar called '{card_name}'. Theme: {theme}. Fantasy trading card portrait, masterpiece, highly detailed. No violence, completely safe for work."
        
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        result = client.models.generate_images(
            model='imagen-3.0-generate-001', # <-- Fixed to the standard public model
            prompt=prompt_text,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="3:4",
                output_mime_type="image/jpeg"
            )
        )
        b64 = base64.b64encode(result.generated_images[0].image.image_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{b64}", None
    except Exception as e:
        return None, str(e) 

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario: return

    st.session_state.theme = theme
    st.session_state.lore = scenario.get("lore", "War has broken out.")
    st.session_state.active_stage = scenario.get("stage")
    db = load_repository()

    def process_deck(cards, is_player):
        deck = []
        for i, card in enumerate(cards * 3): 
            new_card = card.copy()
            new_card['id'] = f"{'p' if is_player else 'e'}_{i}_{random.randint(100,999)}"
            new_card['rarity'] = card.get('rarity', 'Common')
            new_card['desc'] = card.get('desc', 'A combatant enters the fray.')
            new_card['ability_used'] = False
            new_card['is_dead'] = False
            new_card['is_consumed'] = False
            
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
    st.session_state.turn_count = 1
    st.session_state.battle_log = ["The battle begins!"]
    for k in ['selected_attacker', 'selected_buff', 'attacks_used', 'animation_state']:
        if k == 'attacks_used': st.session_state[k] = set()
        elif k == 'animation_state': st.session_state[k] = {}
        else: st.session_state[k] = None
        
    st.session_state.game_active = True
    st.session_state.game_over = False
    st.session_state.winner = None

def play_card(card_id, is_player=True):
    cleanup_dead_cards()
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck
    card_idx = next((i for i, c in enumerate(hand) if c['id'] == card_id), None)
    if card_idx is None: return
    card = hand.pop(card_idx)
    board.append(card)
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} deployed {card['name']}.")
    if deck: hand.append(deck.pop())

def apply_buff(buff_id, target_id):
    cleanup_dead_cards()
    buff_card = next((c for c in st.session_state.hand if c['id'] == buff_id), None)
    target_card = next((c for c in st.session_state.board if c['id'] == target_id), None)
    if not buff_card or not target_card: return
    mods = buff_card.get('stat_modifier', {})
    atk_mod = mods.get('atk', 0)
    def_mod = mods.get('def', 0)
    target_card['atk'] = target_card.get('atk', 0) + atk_mod
    target_card['def'] = target_card.get('def', 0) + def_mod
    buff_card['is_consumed'] = True 
    log_event(f"✨ Applied {buff_card['name']} to {target_card['name']} (+{atk_mod} ATK, +{def_mod} DEF)!")
    st.session_state.animation_state = {'type': 'buff', 'target_id': target_card['id']}
    if st.session_state.deck: st.session_state.hand.append(st.session_state.deck.pop())

def trigger_ability(card_id):
    cleanup_dead_cards()
    card = next((c for c in st.session_state.board if c['id'] == card_id), None)
    if not card: return
    card['ability_used'] = True
    ab_name = card.get('ability', {}).get('name', 'Ability')
    st.session_state.enemy_hp -= 2
    log_event(f"⚡ {card['name']} used {ab_name}! Dealt 2 DMG to Enemy Leader.")
    check_win_condition()

def resolve_attack(attacker_id, target_id):
    cleanup_dead_cards()
    attacker = next((c for c in st.session_state.board if c['id'] == attacker_id), None)
    target = next((c for c in st.session_state.enemy_board if c['id'] == target_id), None)
    if not attacker or not target: return
    atk = int(attacker.get('atk', 0))
    target['def'] = int(target.get('def', 0)) - atk
    log_event(f"🎯 {attacker['name']} hit {target['name']} for {atk} DMG!")
    st.session_state.attacks_used.add(attacker.get('id'))
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id'], 'target_id': target['id']}
    if target['def'] <= 0:
        log_event(f"💀 {target['name']} was destroyed!")
        target['is_dead'] = True 
    check_win_condition()

def resolve_direct_attack(attacker_id):
    cleanup_dead_cards()
    attacker = next((c for c in st.session_state.board if c['id'] == attacker_id), None)
    if not attacker: return
    atk = int(attacker.get('atk', 0))
    st.session_state.enemy_hp -= atk
    st.session_state.attacks_used.add(attacker.get('id'))
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id']}
    log_event(f"💥 {attacker['name']} hit the enemy leader for {atk} DMG!")
    check_win_condition()

def execute_enemy_turn():
    cleanup_dead_cards()
    log_event("--- Enemy Turn ---")
    st.session_state.animation_state = {} 
    if st.session_state.enemy_hand and len(st.session_state.enemy_board) < 5:
        for c in st.session_state.enemy_hand:
            if c.get('type') == 'Attack':
                play_card(c['id'], is_player=False)
                break
    for enemy_card in list(st.session_state.enemy_board):
        if enemy_card.get('type') == 'Attack' and not enemy_card.get('is_dead'):
            atk = int(enemy_card.get('atk', 0))
            valid_targets = [c for c in st.session_state.board if not c.get('is_dead')]
            if valid_targets:
                target = valid_targets[0]
                target['def'] = int(target.get('def', 0)) - atk
                log_event(f"⚔️ Enemy {enemy_card['name']} hit {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 Your {target['name']} was destroyed!")
                    target['is_dead'] = True
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 Enemy {enemy_card['name']} hit YOU for {atk} DMG!")
    check_win_condition()
    st.session_state.turn_count += 1
    log_event("--- Your Turn ---")
    st.session_state.attacks_used = set()

def end_turn():
    st.session_state.selected_attacker = None
    st.session_state.selected_buff = None
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_type, is_enemy=False):
    card_key = f"{location_type}_{card['id']}"

    is_selected_attacker = (not is_enemy and location_type == 'board' and st.session_state.selected_attacker == card.get('id'))
    is_selected_buff = (not is_enemy and location_type == 'hand' and st.session_state.selected_buff == card.get('id'))
    is_targetable_enemy = (is_enemy and location_type == 'eboard' and st.session_state.selected_attacker is not None and not card.get('is_dead'))
    is_targetable_friendly = (not is_enemy and location_type == 'board' and st.session_state.selected_buff is not None and not card.get('is_dead'))

    wrapper_classes = [f"rarity-{card.get('rarity', 'Common')}"]
    if is_selected_attacker or is_selected_buff: wrapper_classes.append("is-selected")
    if is_targetable_enemy or is_targetable_friendly: wrapper_classes.append("is-targetable")
    
    anim_state = st.session_state.get('animation_state', {})
    if anim_state.get('attacker_id') == card['id']: wrapper_classes.append("anim-attack")
    if anim_state.get('target_id') == card['id']: wrapper_classes.append("anim-damage")
    if card.get('is_dead'): wrapper_classes.append("anim-death")
    if card.get('is_consumed'): wrapper_classes.append("anim-consume")

    html = f"<div class='flip-card {' '.join(wrapper_classes)}'>"
    html += "<label style='display:block; width:100%; height:100%; margin:0; cursor:pointer;'>"
    html += "<input type='checkbox' class='flip-checkbox' style='display:none;'>"
    html += "<div class='flip-card-inner'>"
    
    html += "<div class='flip-card-front'>"
    
    fallback_img = base64.b64decode("aHR0cHM6Ly9kdW1teWltYWdlLmNvbS8yNTZ4Mzg0LzFFMUUyNC9GRkZGRkYucG5nP3RleHQ9Tm8rSW1hZ2U=").decode("utf-8")
    
    html += f"<img src='{card.get('image', fallback_img)}' referrerpolicy='no-referrer' onerror=\"this.onerror=null;this.src='{fallback_img}';\" style='width:100%; height:100%; object-fit:cover; opacity:0.9; background-color: #2b2b36;'>"
    
    if card.get('type') == 'Attack':
        html += "<div style='position:absolute; bottom:35px; width:100%; display:flex; justify-content:space-between; padding:0 10px; font-weight:bold; font-size:16px; text-shadow:1px 1px 2px #000;'>"
        html += f"<span style='background:rgba(200,40,40,0.9); padding:2px 8px; border-radius:4px;'>⚔️ {card.get('atk', 0)}</span>"
        html += f"<span style='background:rgba(40,100,200,0.9); padding:2px 8px; border-radius:4px;'>🛡️ {card.get('def', 0)}</span>"
        html += "</div>"
    html += "<div style='position:absolute; bottom:0; width:100%; background:rgba(0,0,0,0.85); padding:8px; border-top:1px solid #555;'>"
    html += f"<h4 style='margin:0; font-size:14px;'>{card['name']}</h4>"
    html += "</div></div>"

    html += "<div class='flip-card-back'>"
    html += "<div style='padding:15px; flex-grow:1; overflow-y:auto;'>"
    html += f"<h4 style='margin:0 0 5px 0; border-bottom:1px solid #555; padding-bottom:5px; font-size:16px;'>{card['name']}</h4>"
    html += f"<p style='margin:0 0 10px 0; font-size:11px; color:#aaa;'>[{card['type']} - {card.get('rarity')}]</p>"
    html += f"<p style='margin:0; font-size:12px; font-style:italic; color:#ddd;'>\"{card.get('desc', 'No lore.')}\"</p>"
    html += "</div>"
    
    if 'ability' in card:
        ab = card['ability']
        html += f"<div style='margin:0 10px 10px 10px; background:rgba(255,255,255,0.1); padding:8px; border-radius:6px; font-size:11px;'><b style='color:#ffeb3b;'>✨ {ab.get('name','Ability')}</b><br>{ab.get('desc','')}</div>"
    
    if card.get('type') == 'Attack':
        html += f"<div style='padding:10px; display:flex; justify-content:space-between; font-weight:bold; font-size:16px; border-top:1px solid #555; background:rgba(0,0,0,0.4);'><span>⚔️ {card.get('atk', 0)}</span><span>🛡️ {card.get('def', 0)}</span></div>"
    elif card.get('type') == 'Buff':
        mods = card.get('stat_modifier', {})
        html += f"<div style='padding:10px; font-weight:bold; font-size:14px; border-top:1px solid #555; background:rgba(0,0,0,0.4); text-align:center;'>Buff: +{mods.get('atk',0)} ATK / +{mods.get('def',0)} DEF</div>"

    html += "</div></div></label></div>"
    st.markdown(html, unsafe_allow_html=True)

    # --- Interaction Buttons ---
    is_disabled = card.get('is_dead', False) or card.get('is_consumed', False)
    
    if not is_disabled:
        if not is_enemy and location_type == 'hand':
            if card.get('type') == 'Attack':
                if st.button("Deploy", key=f"play_{card_key}", type="primary"):
                    play_card(card['id'], is_player=True); st.rerun()
            elif card.get('type') == 'Buff':
                if is_selected_buff:
                    if st.button("Cancel", key=f"cancel_{card_key}"):
                        st.session_state.selected_buff = None; st.rerun()
                else:
                    if st.button("Use Buff", key=f"use_{card_key}", type="primary"):
                        st.session_state.selected_buff = card['id']
                        st.session_state.selected_attacker = None; st.rerun()

        elif not is_enemy and location_type == 'board':
            if is_targetable_friendly:
                if st.button("Apply Buff Here", key=f"apply_{card_key}", type="primary"):
                    apply_buff(st.session_state.selected_buff, card['id'])
                    st.session_state.selected_buff = None; st.rerun()
            
            elif card.get('type') == 'Attack':
                can_attack = card.get('id') not in st.session_state.attacks_used
                if is_selected_attacker:
                    if st.button("Cancel", key=f"cancel_atk_{card_key}"):
                        st.session_state.selected_attacker = None; st.rerun()
                else:
                    if st.button("⚔️ Attack", key=f"atk_{card_key}", type="primary", disabled=not can_attack):
                        st.session_state.selected_attacker = card['id']; st.rerun()
                
                if 'ability' in card and not card.get('ability_used', False):
                    if st.button("✨ Ability", key=f"ab_{card_key}"):
                        trigger_ability(card['id']); st.rerun()

        elif is_enemy and location_type == 'eboard' and st.session_state.selected_attacker:
            if st.button("🎯 Strike", key=f"tgt_{card_key}", type="primary"):
                resolve_attack(st.session_state.selected_attacker, card['id'])
                st.session_state.selected_attacker = None; st.rerun()

        # --- THE LAZY LOADER BUTTON ---
        if not card.get('has_ai_art', False) and not is_enemy:
            if st.button("🎨 Paint AI Art", key=f"paint_{card_key}"):
                api_key = st.secrets.get("GEMINI_API_KEY", "")
                with st.spinner(f"Painting {card['name']}..."):
                    new_img, error_msg = fetch_ai_image(card['name'], card.get('type', 'Attack'), st.session_state.theme, api_key)
                    if new_img:
                        save_to_repository(card['name'], new_img)
                        sync_art_across_game(card['name'], new_img)
                        st.rerun()
                    else:
                        # EXACT ERROR DIAGNOSTICS:
                        st.error(f"Generation Failed: {error_msg}")

# --- Main UI Rendering ---
if not st.session_state.game_active:
    st.title("🃏 AI Lore Battler")
    st.markdown("Enter a theme to generate decks, lore, and artwork.")
    theme_input = st.text_input("Theme (e.g., 'Old School RuneScape', 'Cyberpunk Pirates'):")
    if st.button("Generate Scenario & Start", type="primary"):
        if theme_input:
            with st.spinner("Forging cards... Game starts instantly, paint art at your own pace!"):
                setup_game(theme_input)
            st.rerun()

elif st.session_state.game_over:
    if st.session_state.winner == "Player": st.balloons(); st.success("# 🏆 VICTORY IS YOURS!")
    else: st.snow(); st.error("# 💀 DEFEAT...")
    
    with st.expander("📖 Scenario Lore", expanded=True): st.write(st.session_state.lore)
        
    if st.button("Return to Main Menu", type="primary"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()

else:
    with st.expander("📖 Scenario Lore", expanded=False): st.write(st.session_state.lore)
    st.write("---")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        if st.session_state.selected_buff: st.info("⬆️ Select a friendly card to buff.")
        elif st.session_state.selected_attacker: st.warning("🎯 Select an enemy target.")
        else: st.success("🟢 Awaiting Orders")
    with col2: st.markdown(f"<h3 style='color:#ff4a4a; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3: st.markdown(f"<h3 style='color:#4a8cff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
    with col4:
        if st.button("⏭️ End Turn", use_container_width=True, type="primary"): end_turn(); st.rerun()

    st.markdown("<div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 15px; border: 1px solid #444; margin-bottom: 20px;'>", unsafe_allow_html=True)
    col_main, col_log = st.columns([4, 1])

    with col_main:
        st.markdown("<h4 style='color:#ff4a4a; text-align:center;'>👿 Enemy Field</h4>", unsafe_allow_html=True)
        if st.session_state.enemy_board:
            eboard_cols = st.columns(max(len(st.session_state.enemy_board), 1))
            for i, card in enumerate(st.session_state.enemy_board):
                with eboard_cols[i]: render_card(card, "eboard", is_enemy=True)
        else:
            st.caption("Enemy field is empty.")
            if st.session_state.selected_attacker:
                if st.button("🎯 Target Enemy Leader", key="tgt_enemy", type="primary", use_container_width=True):
                    resolve_direct_attack(st.session_state.selected_attacker)
                    st.session_state.selected_attacker = None; st.rerun()

        st.markdown("<hr style='border-color: #555;'>", unsafe_allow_html=True)

        st.markdown("<h4 style='color:#4a8cff; text-align:center;'>🛡️ Your Field</h4>", unsafe_allow_html=True)
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]: render_card(card, "board", is_enemy=False)
        else:
            st.caption("Your field is empty.")

    with col_log:
        st.markdown("<b>📜 Battle Log</b>", unsafe_allow_html=True)
        for log in st.session_state.battle_log: 
            st.markdown(f"<div style='font-size:13px; margin-bottom:6px; padding:6px; background:rgba(255,255,255,0.05); border-radius:6px; border-left: 3px solid #666;'>{log}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True) 

    st.markdown("<h3 style='text-align:center;'>🖐️ Your Hand</h3>", unsafe_allow_html=True)
    if st.session_state.hand:
        hand_cols = st.columns(len(st.session_state.hand))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]: render_card(card, "hand", is_enemy=False)

    st.write("---")
    if st.button("Surrender & Restart"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()