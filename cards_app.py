import streamlit as st
import random
import json
import re
import urllib.parse
import textwrap
try:
    import requests
except Exception:
    requests = None
import base64

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")

# --- Global CSS ---
st.markdown("""
<style>
.card-shell { transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease; }
.card-shell:hover { transform: translateY(-2px) scale(1.01); filter: brightness(1.03); }
.card-shell.targetable { cursor: crosshair; }
.card-shell.selected { transform: translateY(-3px) scale(1.02); }
</style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
state_defaults = {
    'game_active': False, 'game_over': False, 'winner': None,
    'deck': [], 'hand': [], 'board': [],
    'enemy_deck': [], 'enemy_hand': [], 'enemy_board': [],
    'player_hp': 30, 'enemy_hp': 30,
    'active_stage': None, 'lore': "",
    'turn_count': 1, 'battle_log': [],
    'selected_attacker': None, 'attacks_used': set()
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

# --- Live API Integration ---
def call_llm_api(theme):
    """Calls the Gemini API to generate the card game scenario."""
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY is missing. Please add it to your .streamlit/secrets.toml file.")
        return None

    system_prompt = f"""
    You are an expert card game designer. Create a balanced, thematic card game scenario based ONLY on this theme: '{theme}'.
    
    Return ONLY a valid JSON object with this exact structure (no markdown formatting, no text outside the JSON):
    {{
      "lore": "Two paragraphs describing the conflict, the setting, and the two opposing factions.",
      "stage": {{"name": "Stage Name", "type": "Stage", "stage_effect": "acid_rain", "desc": "effect desc", "visuals": {{"css_gradient": "linear-gradient(to bottom, #111111, #444444)", "weather_overlay": "none"}}}},
      "player_cards": [ Generate exactly 8 cards (Attack and Buff) for the protagonist faction ],
      "enemy_cards": [ Generate exactly 8 cards (Attack and Buff) for the antagonist faction ]
    }}
    
    Rules for cards:
    - Attack cards must have 'atk' (1-8), 'def' (1-8), and optionally an 'ability' object (trigger, effect_type).
    - Buff cards must have 'stat_modifier' (e.g. {{"atk": 2, "def": 0}}) and 'duration_turns'.
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

def fetch_real_ai_image(prompt: str) -> str:
    safe_prompt = urllib.parse.quote(prompt + ", beautiful digital art, fantasy trading card illustration, masterpiece")
    seed = random.randint(1, 100000)
    return f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){safe_prompt}?width=256&height=384&nologo=true&seed={seed}"

@st.cache_data(show_spinner=False, ttl=60*60)
def _image_url_to_data_uri(url: str):
    if not url or requests is None: return None
    try:
        # FIX 1: Pretend to be a real web browser to bypass anti-bot blocks
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get('content-type', '').split(';')[0].strip().lower()
        if not content_type.startswith('image/'): return None
        b64 = base64.b64encode(r.content).decode('ascii')
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        print(f"Failed to fetch image: {e}")
        return None

def get_renderable_image_src(url: str) -> str:
    return _image_url_to_data_uri(url) or url

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario: return

    st.session_state.lore = scenario.get("lore", "War has broken out.")
    st.session_state.active_stage = scenario.get("stage")

    p_deck = []
    for i, card in enumerate(scenario.get("player_cards", []) * 4):
        card['id'] = f"p_{i}"
        card['is_flipped'] = False
        card['image'] = fetch_real_ai_image(f"{card['name']}, {theme} protagonist")
        p_deck.append(card.copy())
    random.shuffle(p_deck)
    st.session_state.deck = p_deck
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(4)]

    e_deck = []
    for i, card in enumerate(scenario.get("enemy_cards", []) * 4):
        card['id'] = f"e_{i}"
        card['is_flipped'] = False
        card['image'] = fetch_real_ai_image(f"{card['name']}, {theme} antagonist villain")
        e_deck.append(card.copy())
    random.shuffle(e_deck)
    st.session_state.enemy_deck = e_deck
    st.session_state.enemy_hand = [st.session_state.enemy_deck.pop() for _ in range(4)]

    st.session_state.player_hp = 30
    st.session_state.enemy_hp = 30
    st.session_state.turn_count = 1
    st.session_state.battle_log = ["The battle begins!"]
    st.session_state.selected_attacker = None
    st.session_state.attacks_used = set()
    st.session_state.game_active = True
    st.session_state.game_over = False
    st.session_state.winner = None

def play_card(card_index, is_player=True):
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck

    card = hand.pop(card_index)
    card['is_flipped'] = False
    board.append(card)
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} played {card['name']}.")
    if deck: hand.append(deck.pop())

def _find_player_board_index_by_id(card_id: str):
    for idx, c in enumerate(st.session_state.board):
        if c.get('id') == card_id: return idx
    return None

def resolve_attack(attacker_idx: int, target_idx: int):
    if attacker_idx is None or target_idx is None: return
    if attacker_idx < 0 or attacker_idx >= len(st.session_state.board): return
    if target_idx < 0 or target_idx >= len(st.session_state.enemy_board): return

    attacker = st.session_state.board[attacker_idx]
    target = st.session_state.enemy_board[target_idx]

    if attacker.get('type') != 'Attack': return

    atk = int(attacker.get('atk', 0))
    target['def'] = int(target.get('def', 0)) - atk
    log_event(f"🎯 {attacker['name']} hit {target['name']} for {atk} DMG!")
    st.session_state.attacks_used.add(attacker.get('id'))

    if target['def'] <= 0:
        log_event(f"💀 {target['name']} was destroyed!")
        st.session_state.enemy_board.pop(target_idx)
    
    check_win_condition()

def resolve_direct_attack(attacker_idx: int):
    if attacker_idx is None: return
    if attacker_idx < 0 or attacker_idx >= len(st.session_state.board): return
    if st.session_state.enemy_board: return

    attacker = st.session_state.board[attacker_idx]
    if attacker.get('type') != 'Attack': return

    atk = int(attacker.get('atk', 0))
    st.session_state.enemy_hp -= atk
    st.session_state.attacks_used.add(attacker.get('id'))
    log_event(f"💥 {attacker['name']} hit the enemy for {atk} DMG!")
    check_win_condition()

def execute_enemy_turn():
    log_event("--- Enemy Turn ---")
    if st.session_state.enemy_hand and len(st.session_state.enemy_board) < 5:
        play_card(0, is_player=False)

    for enemy_card in list(st.session_state.enemy_board):
        if enemy_card.get('type') == 'Attack' and not enemy_card.get('active_status'):
            atk = int(enemy_card.get('atk', 0))
            if st.session_state.board:
                target = st.session_state.board[0]
                target['def'] = int(target.get('def', 0)) - atk
                log_event(f"⚔️ {enemy_card['name']} hit {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 {target['name']} was destroyed!")
                    if st.session_state.selected_attacker == target.get('id'):
                        st.session_state.selected_attacker = None
                    st.session_state.board.pop(0)
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 {enemy_card['name']} hit YOU for {atk} DMG!")

    check_win_condition()
    st.session_state.turn_count += 1
    log_event("--- Your Turn ---")
    st.session_state.attacks_used = set()

def end_turn():
    st.session_state.selected_attacker = None
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_index, location_type, is_enemy=False):
    card_key = f"{location_type}_{card['id']}"

    if st.button("🔄 Flip", key=f"btn_{card_key}"):
        card['is_flipped'] = not card.get('is_flipped', False)
        st.rerun()

    is_selected_attacker = (not is_enemy and location_type == 'board' and st.session_state.selected_attacker == card.get('id'))
    border_color = "#ff4a4a" if is_enemy else "#4a8cff"
    highlight = "0 0 0 4px rgba(74,140,255,0.35), 0 0 18px rgba(74,140,255,0.45)" if is_selected_attacker else "0 4px 8px rgba(0,0,0,0.6)"

    is_targetable_enemy = (is_enemy and location_type == 'eboard' and st.session_state.selected_attacker is not None)
    target_glow = "0 0 0 4px rgba(255,205,0,0.35), 0 0 18px rgba(255,205,0,0.35)" if is_targetable_enemy else ""

    extra_class = " selected" if is_selected_attacker else ""
    extra_class += " targetable" if is_targetable_enemy else ""

    card_html = f"""
<div class='card-shell{extra_class}' style='
    background-color: #1e1e1e; border: 3px solid {border_color}; border-radius: 12px;
    box-shadow: {target_glow if (is_targetable_enemy and not is_selected_attacker) else highlight};
    height: 320px; overflow: hidden; position: relative; color: white; font-family: sans-serif;
'>
"""
    if not card.get('is_flipped', False):
        # FIX 2: Removed referrerpolicy and crossorigin from the img tag
        card_html += f"""
<div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%;'>
    <img src='{get_renderable_image_src(card.get("image", ""))}' style='width: 100%; height: 100%; object-fit: cover; opacity: 0.85;'>
</div>
<div style='position: absolute; bottom: 0; left: 0; width: 100%; background: rgba(0,0,0,0.82); padding: 8px; border-top: 1px solid {border_color};'>
    <h4 style='margin: 0; font-size: 16px; text-align: center;'>{card['name']}</h4>
</div>
"""
    else:
        atk_val = card.get('atk', card.get('stat_modifier', {}).get('atk', '-'))
        def_val = card.get('def', card.get('stat_modifier', {}).get('def', '-'))
        card_html += f"""
<div style='padding: 15px; height: 100%; display: flex; flex-direction: column;'>
    <h4 style='margin-top: 0; color: {border_color}; border-bottom: 1px solid #444; padding-bottom: 5px;'>{card['name']}</h4>
    <p style='font-size: 12px; color: #aaa; margin-bottom: 10px;'>[{card['type']}]</p>
    <p style='font-size: 14px; flex-grow: 1; overflow-y: auto;'><i>"{card.get('desc', '')}"</i></p>
"""
        if 'ability' in card:
            ab = card['ability']
            card_html += f"<div style='background: #333; padding: 5px; border-radius: 5px; margin-bottom: 10px;'><b style='font-size: 12px;'>✨ {ab.get('name','Ability')}</b><br><span style='font-size: 11px;'>Trigger: {ab.get('trigger','')}</span></div>"

        card_html += f"<div style='display:flex;justify-content:space-between;font-weight:bold;font-size:18px;border-top:1px solid #444;padding-top:10px;'><span>⚔️ {atk_val}</span><span>🛡️ {def_val}</span></div></div>"
    
    card_html += "</div>"
    st.markdown(textwrap.dedent(card_html).strip(), unsafe_allow_html=True)

    if not is_enemy and location_type == 'hand':
        if st.button("Play Card", key=f"play_{card_key}", type="primary", use_container_width=True):
            play_card(location_index, is_player=True); st.rerun()

    if not is_enemy and location_type == 'board':
        can_attack = (card.get('type') == 'Attack') and (card.get('id') not in st.session_state.attacks_used)
        if st.session_state.selected_attacker == card.get('id'):
            if st.button("❌ Cancel", key=f"cancel_atk_{card_key}", use_container_width=True):
                st.session_state.selected_attacker = None; st.rerun()
        else:
            attack_label = "⚔️ Attack" if can_attack else ("⛔ Exhausted" if card.get('type') == 'Attack' else "(No Attack)")
            if st.button(attack_label, key=f"atk_{card_key}", use_container_width=True, disabled=not can_attack):
                st.session_state.selected_attacker = card.get('id')
                log_event(f"🟦 Selected attacker: {card['name']}. Choose a target.")
                st.rerun()

    if is_enemy and location_type == 'eboard' and st.session_state.selected_attacker:
        attacker_idx = _find_player_board_index_by_id(st.session_state.selected_attacker)
        attacker_valid = attacker_idx is not None and attacker_idx < len(st.session_state.board) and st.session_state.board[attacker_idx].get('type') == 'Attack' and (st.session_state.board[attacker_idx].get('id') not in st.session_state.attacks_used)
        if st.button("🎯 Target", key=f"tgt_{card_key}", type="primary", use_container_width=True, disabled=not attacker_valid):
            if attacker_valid: resolve_attack(attacker_idx, location_index)
            st.session_state.selected_attacker = None
            st.rerun()

# --- Main UI Rendering ---
if st.session_state.active_stage:
    visuals = st.session_state.active_stage.get('visuals', {})
    bg_gradient = visuals.get('css_gradient', 'linear-gradient(to bottom, #111, #222)')
    st.markdown(f"<style>.stApp {{ background: {bg_gradient}; background-attachment: fixed; }}</style>", unsafe_allow_html=True)

if not st.session_state.game_active:
    st.title("🃏 AI Lore Battler")
    st.markdown("Enter a theme. The AI will write the lore, design the factions, and generate the card art.")
    theme_input = st.text_input("Theme (e.g., 'Steampunk Pirates vs Clockwork Navy'):")
    if st.button("Generate Scenario & Start", type="primary"):
        if theme_input:
            with st.spinner("Calling Gemini API to write lore and generate stats (this takes a few seconds)..."):
                setup_game(theme_input)
            st.rerun()

elif st.session_state.game_over:
    if st.session_state.winner == "Player": 
        st.balloons(); st.success("# 🏆 VICTORY IS YOURS!")
    else: 
        st.snow(); st.error("# 💀 DEFEAT...")
    
    with st.expander("📖 Scenario Lore", expanded=True): st.write(st.session_state.lore)
        
    if st.button("Return to Main Menu", type="primary"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()

else:
    with st.expander("📖 Scenario Lore", expanded=False): st.write(st.session_state.lore)

    st.write("---")
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        if st.session_state.active_stage: st.success(f"**🌍 Active Stage:** {st.session_state.active_stage['name']}")
    with col2: st.markdown(f"<h3 style='color:#ff4a4a; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3: st.markdown(f"<h3 style='color:#4a8cff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
    with col4:
        if st.button("⏭️ End Turn", use_container_width=True, type="primary"):
            end_turn(); st.rerun()

    st.markdown("<div style='background: rgba(0,0,0,0.5); padding: 20px; border-radius: 15px; border: 1px solid #444; margin-bottom: 20px;'>", unsafe_allow_html=True)

    col_main, col_log = st.columns([4, 1])

    with col_main:
        st.markdown("<h4 style='color:#ff4a4a; text-align:center;'>👿 Enemy Field</h4>", unsafe_allow_html=True)
        if st.session_state.enemy_board:
            eboard_cols = st.columns(max(len(st.session_state.enemy_board), 1))
            for i, card in enumerate(st.session_state.enemy_board):
                with eboard_cols[i]: render_card(card, i, "eboard", is_enemy=True)
        else:
            st.caption("Enemy field is empty.")
            if st.session_state.selected_attacker:
                attacker_idx = _find_player_board_index_by_id(st.session_state.selected_attacker)
                attacker_valid = (attacker_idx is not None and attacker_idx < len(st.session_state.board) and st.session_state.board[attacker_idx].get('type') == 'Attack' and (st.session_state.board[attacker_idx].get('id') not in st.session_state.attacks_used))
                if st.button("🎯 Target Enemy", key="tgt_enemy", type="primary", use_container_width=True, disabled=not attacker_valid):
                    if attacker_valid: resolve_direct_attack(attacker_idx)
                    st.session_state.selected_attacker = None; st.rerun()

        st.markdown("<hr style='border-color: #555;'>", unsafe_allow_html=True)

        st.markdown("<h4 style='color:#4a8cff; text-align:center;'>🛡️ Your Field</h4>", unsafe_allow_html=True)
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]: render_card(card, i, "board", is_enemy=False)
        else:
            st.caption("Your field is empty.")

        if st.session_state.selected_attacker: st.info("Attacker selected — click 🎯 Target on an enemy card.")

    with col_log:
        st.markdown("<b>📜 Battle Log</b>", unsafe_allow_html=True)
        for log in st.session_state.battle_log: st.markdown(f"<div style='font-size:12px; margin-bottom:5px; padding:5px; background:rgba(255,255,255,0.05); border-radius:4px;'>{log}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True) 

    st.markdown("<h3 style='text-align:center;'>🖐️ Your Hand</h3>", unsafe_allow_html=True)
    if st.session_state.hand:
        hand_cols = st.columns(len(st.session_state.hand))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]: render_card(card, i, "hand", is_enemy=False)

    st.write("---")
    if st.button("Surrender & Restart"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()