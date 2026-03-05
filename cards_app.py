import streamlit as st
import random
import json
import re

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide")

# --- Initialize Session State ---
if 'deck' not in st.session_state: st.session_state.deck = []
if 'hand' not in st.session_state: st.session_state.hand = []
if 'board' not in st.session_state: st.session_state.board = []
if 'enemy_deck' not in st.session_state: st.session_state.enemy_deck = []
if 'enemy_hand' not in st.session_state: st.session_state.enemy_hand = []
if 'enemy_board' not in st.session_state: st.session_state.enemy_board = []
if 'player_hp' not in st.session_state: st.session_state.player_hp = 20
if 'enemy_hp' not in st.session_state: st.session_state.enemy_hp = 20
if 'active_stage' not in st.session_state: st.session_state.active_stage = None
if 'image_cache' not in st.session_state: st.session_state.image_cache = {}
if 'generated_types' not in st.session_state: st.session_state.generated_types = {"Attack": False, "Buff": False, "Stage": False}
if 'turn_count' not in st.session_state: st.session_state.turn_count = 1
if 'battle_log' not in st.session_state: st.session_state.battle_log = []

def log_event(message):
    st.session_state.battle_log.insert(0, message)
    if len(st.session_state.battle_log) > 5:
        st.session_state.battle_log.pop()

# --- Real API Integration Blueprint ---
def call_llm_api(theme):
    """Mocks the LLM API call with robust JSON parsing."""
    try:
        # MOCK RESPONSE
        raw_response_text = """```json
        [
            {
                "name": "Heavy Bruiser", "type": "Attack", "atk": 5, "def": 5,
                "ability": {"name": "Slam", "trigger": "Active", "effect_type": "status", "status": "stun", "duration_turns": 1},
                "desc": "Hits hard, takes hits well."
            },
            {
                "name": "Tactical Strike", "type": "Buff", "stat_modifier": {"atk": 2, "def": 0},
                "special_effect": "none", "duration_turns": 1, "desc": "A quick boost to offensive capabilities."
            },
            {
                "name": "Toxic Wasteland", "type": "Stage", "stage_effect": "acid_rain", 
                "desc": "All Attack cards lose 1 DEF per turn.",
                "visuals": {"css_gradient": "linear-gradient(to bottom, #2E3B32, #1a2a6c)", "weather_overlay": "rain"}
            }
        ]
        ```"""
        
        cleaned_text = re.sub(r'```json\n|\n```|```', '', raw_response_text).strip()
        deck_data = json.loads(cleaned_text)
        
        if not isinstance(deck_data, list): raise ValueError("AI did not return a JSON array.")
        return deck_data * 4 # Make a deck of 12 cards

    except Exception as e:
        st.error(f"API Error: {e}")
        return []

def generate_image(prompt, card_type):
    """Mocks image generation."""
    if not st.session_state.generated_types[card_type]:
        st.session_state.generated_types[card_type] = True
        return f"[https://via.placeholder.com/200/222222/FFFFFF?text=](https://via.placeholder.com/200/222222/FFFFFF?text=){card_type}+Image"
    else:
        colors = {"Attack": "#992222", "Buff": "#229922", "Stage": "#222299"}
        return colors.get(card_type, "#555555")

# --- Game Logic Functions ---
def build_decks(theme):
    raw_cards = call_llm_api(theme)
    enemy_raw = call_llm_api(f"Corrupted {theme}") 
    
    if not raw_cards or not enemy_raw: return
        
    # Build Player Deck
    new_deck = []
    for i, card in enumerate(raw_cards):
        card['id'] = f"player_{card['name'].replace(' ', '_')}_{i}" 
        card['is_flipped'] = False
        if card['name'] not in st.session_state.image_cache:
            st.session_state.image_cache[card['name']] = generate_image(f"Card art: {card['name']}", card['type'])
        card['image'] = st.session_state.image_cache[card['name']]
        new_deck.append(card.copy())
        
    random.shuffle(new_deck)
    st.session_state.deck = new_deck
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(3)]

    # Build Enemy Deck
    new_enemy_deck = []
    for i, card in enumerate(enemy_raw):
        card['id'] = f"enemy_{card['name'].replace(' ', '_')}_{i}"
        card['is_flipped'] = False
        # slightly alter enemy names for flavor
        card['name'] = f"Dark {card['name']}"
        if card['name'] not in st.session_state.image_cache:
            st.session_state.image_cache[card['name']] = generate_image(f"Villain card: {card['name']}", card['type'])
        card['image'] = st.session_state.image_cache[card['name']]
        new_enemy_deck.append(card.copy())
            
    random.shuffle(new_enemy_deck)
    st.session_state.enemy_deck = new_enemy_deck
    st.session_state.enemy_hand = [st.session_state.enemy_deck.pop() for _ in range(3)]
    
    st.session_state.player_hp = 20
    st.session_state.enemy_hp = 20
    st.session_state.battle_log = ["Match started!"]

def play_card(card_index, is_player=True):
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck
    
    card = hand.pop(card_index)
    card['is_flipped'] = False
    
    if card['type'] == 'Stage':
        st.session_state.active_stage = card
        owner = "Player" if is_player else "Enemy"
        log_event(f"🌍 {owner} changed stage to {card['name']}!")
    else:
        board.append(card)
        
    if deck: hand.append(deck.pop())

def trigger_ability(board_index, is_player=True):
    board = st.session_state.board if is_player else st.session_state.enemy_board
    target_board = st.session_state.enemy_board if is_player else st.session_state.board
    
    card = board[board_index]
    ability = card.get('ability', {})
    
    if ability.get('effect_type') == 'status' and target_board:
        target_idx = 0 # Simple auto-target first card for prototype
        target_board[target_idx]['active_status'] = ability['status']
        target_board[target_idx]['status_duration'] = ability['duration_turns']
        log_event(f"✨ {card['name']} inflicted {ability['status'].upper()} on {target_board[target_idx]['name']}!")
        
    card['ability_used'] = True

def execute_enemy_turn():
    """AI logic: Play first card, then attack."""
    log_event("--- Enemy Turn ---")
    
    if st.session_state.enemy_hand:
        # Simple AI: Just play the first card in hand
        play_card(0, is_player=False)
        
    # Combat Phase
    for enemy_card in st.session_state.enemy_board:
        if enemy_card['type'] == 'Attack' and enemy_card.get('active_status') not in ['sleep', 'stun']:
            atk = enemy_card.get('atk', 0)
            
            if st.session_state.board:
                target = st.session_state.board[0]
                target['def'] = target.get('def', 0) - atk
                log_event(f"⚔️ {enemy_card['name']} attacked {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 Your {target['name']} was destroyed!")
                    st.session_state.board.pop(0)
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 {enemy_card['name']} attacked YOU for {atk} DMG!")

    st.session_state.turn_count += 1
    log_event("--- Player Turn ---")

def end_turn():
    # 1. Apply Stage Effects
    if st.session_state.active_stage and st.session_state.active_stage.get('stage_effect') == "acid_rain":
        for b in [st.session_state.board, st.session_state.enemy_board]:
            for card in b:
                if card['type'] == 'Attack' and 'def' in card:
                    card['def'] = max(0, card['def'] - 1) 

    # 2. Process Status Timers
    for b in [st.session_state.board, st.session_state.enemy_board]:
        for card in b:
            if card.get('status_duration', 0) > 0:
                card['status_duration'] -= 1
                if card['status_duration'] <= 0:
                    card['active_status'] = None
                    
    # 3. Trigger Enemy AI
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_index, location_type, is_enemy=False):
    card_key = f"{location_type}_{card['id']}"
    
    if st.button("🔄 Flip", key=f"btn_{card_key}"):
        card['is_flipped'] = not card.get('is_flipped', False)
        st.rerun()

    bg_color = "#2b2b2b" if card['is_flipped'] else "transparent"
    border = "2px solid #ff4444" if is_enemy else "2px solid #4488ff"
    st.markdown(f"<div style='background-color: {bg_color}; padding: 10px; border-radius: 10px; border: {border}; min-height: 250px;'>", unsafe_allow_html=True)
    
    st.markdown(f"**{card['name']}**")

    if not card.get('is_flipped', False):
        if card['image'].startswith('http'): st.image(card['image'], use_container_width=True)
        else: st.markdown(f"<div style='height: 120px; background-color: {card['image']}; border-radius: 5px;'></div>", unsafe_allow_html=True)
        
        if 'atk' in card or 'stat_modifier' in card:
            atk_val = card.get('atk', card.get('stat_modifier', {}).get('atk', 0))
            def_val = card.get('def', card.get('stat_modifier', {}).get('def', 0))
            st.write(f"⚔️ {atk_val} | 🛡️ {def_val}")
    else:
        st.caption(f"Type: {card['type']}")
        st.write(f"*{card['desc']}*")
        if 'atk' in card or 'stat_modifier' in card:
            st.markdown(f"**Stats:** ⚔️ {card.get('atk', 0)} | 🛡️ {card.get('def', 0)}")
        if 'ability' in card:
            ab = card['ability']
            st.markdown(f"**Ability:** {ab['name']}")
            st.caption(f"Trigger: {ab['trigger']} | Effect: {ab.get('effect_type', 'special')}")

    st.markdown("</div>", unsafe_allow_html=True)

    if card.get('active_status'): st.error(f"⚠️ {card['active_status'].upper()} ({card['status_duration']}t)")
    
    if not is_enemy:
        if location_type == 'hand':
            if st.button("Play Card", key=f"play_{card_key}", type="primary"):
                play_card(location_index, is_player=True)
                st.rerun()
        elif location_type == 'board':
            if 'ability' in card and card['ability']['trigger'] == 'Active' and not card.get('ability_used', False):
                if st.button("Use Ability", key=f"ab_{card_key}"):
                    trigger_ability(location_index, is_player=True)
                    st.rerun()

# --- Main UI Rendering ---
if st.session_state.active_stage:
    visuals = st.session_state.active_stage.get('visuals', {})
    bg_gradient = visuals.get('css_gradient', 'linear-gradient(to bottom, #111111, #222222)')
    weather = visuals.get('weather_overlay', 'none')
    custom_css = f"<style>.stApp {{ background: {bg_gradient}; background-attachment: fixed; transition: background 1s ease; }}</style>"
    if weather == 'rain':
        custom_css += """<style>.weather-layer { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 999; background-image: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0.2) 50%, rgba(255,255,255,0)); background-size: 5px 20px; animation: rainDrop 0.5s linear infinite; } @keyframes rainDrop { 0% { background-position: 0px 0px; } 100% { background-position: 20px 100vh; } }</style><div class="weather-layer"></div>"""
    st.markdown(custom_css, unsafe_allow_html=True)

st.title("🃏 AI Theme Battler")

if not st.session_state.deck:
    theme_input = st.text_input("Enter a Theme to generate Decks (e.g., 'Cyberpunk', 'Fantasy'):")
    if st.button("Start Game"):
        if theme_input:
            with st.spinner("Forging cards..."): build_decks(theme_input)
            st.rerun()

if st.session_state.deck or st.session_state.board:
    # Top Bar: Info & Controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        if st.session_state.active_stage: st.success(f"**🌍 Stage:** {st.session_state.active_stage['name']}")
        else: st.info("🌍 Neutral Ground.")
    with col2: st.markdown(f"<h3 style='color:#ff4444; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3: st.markdown(f"<h3 style='color:#4488ff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
    with col4:
        if st.button("⏭️ End Turn", use_container_width=True, type="primary"):
            end_turn()
            st.rerun()

    # Layout: Enemy Board -> Player Board -> Player Hand
    st.write("---")
    
    col_main, col_log = st.columns([4, 1])
    
    with col_main:
        # Enemy Board
        st.subheader("👿 Enemy Field")
        if st.session_state.enemy_board:
            eboard_cols = st.columns(max(len(st.session_state.enemy_board), 1))
            for i, card in enumerate(st.session_state.enemy_board):
                with eboard_cols[i]: render_card(card, i, "eboard", is_enemy=True)
        else: st.caption("Enemy field is empty.")

        st.write("---")
        
        # Player Board
        st.subheader("🛡️ Your Field")
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]: render_card(card, i, "board", is_enemy=False)
        else: st.caption("Your field is empty.")

        st.write("---")
        
        # Player Hand
        st.subheader("🖐️ Your Hand")
        hand_cols = st.columns(max(len(st.session_state.hand), 1))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]: render_card(card, i, "hand", is_enemy=False)
            
    with col_log:
        st.subheader("📜 Battle Log")
        for log in st.session_state.battle_log:
            st.caption(log)
            
    if st.button("Surrender & Restart"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()