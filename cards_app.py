import streamlit as st
import random
import json
import re
import urllib.parse
import textwrap

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")


# --- Global CSS (board feel + hover/target cues) ---
st.markdown("""
<style>
/* Card interaction CSS */
.card-shell { transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease; }
.card-shell:hover { transform: translateY(-2px) scale(1.01); filter: brightness(1.03); }
.card-shell.targetable { cursor: crosshair; }
.card-shell.selected { transform: translateY(-3px) scale(1.02); }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
if 'game_active' not in st.session_state: st.session_state.game_active = False
if 'deck' not in st.session_state: st.session_state.deck = []
if 'hand' not in st.session_state: st.session_state.hand = []
if 'board' not in st.session_state: st.session_state.board = []
if 'enemy_deck' not in st.session_state: st.session_state.enemy_deck = []
if 'enemy_hand' not in st.session_state: st.session_state.enemy_hand = []
if 'enemy_board' not in st.session_state: st.session_state.enemy_board = []
if 'player_hp' not in st.session_state: st.session_state.player_hp = 30
if 'enemy_hp' not in st.session_state: st.session_state.enemy_hp = 30
if 'active_stage' not in st.session_state: st.session_state.active_stage = None
if 'lore' not in st.session_state: st.session_state.lore = ""
if 'turn_count' not in st.session_state: st.session_state.turn_count = 1
if 'battle_log' not in st.session_state: st.session_state.battle_log = []
# NEW: interactive targeting state
if 'selected_attacker' not in st.session_state: st.session_state.selected_attacker = None  # stores attacker card id (player board)
# NEW: per-turn attack exhaustion tracking
if 'attacks_used' not in st.session_state: st.session_state.attacks_used = set()  # card ids that already attacked this turn

def log_event(message: str):
    st.session_state.battle_log.insert(0, message)
    if len(st.session_state.battle_log) > 6:
        st.session_state.battle_log.pop()

# --- Real API Integration ---
def call_llm_api(theme):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    """
    To use real AI: 
    1. pip install google-genai (or openai)
    2. Uncomment the API code below and add your key.
    """

    system_prompt = f"""
    Create a card game scenario based on the theme: '{theme}'.
    Return ONLY a JSON object with this exact structure:
    {{
      "lore": "Two paragraphs describing the conflict, the setting, and the two opposing factions.",
      "stage": {{"name": "Stage Name", "type": "Stage", "stage_effect": "acid_rain", "desc": "effect desc", "visuals": {{"css_gradient": "linear-gradient(...)", "weather_overlay": "rain"}}}},
      "player_cards": [ Generate 8 cards (Attack and Buff) for the protagonist faction ],
      "enemy_cards": [ Generate 8 cards (Attack and Buff) for the antagonist faction ]
    }}
    Attack cards need 'atk', 'def', and optionally an 'ability' object. 
    Buff cards need 'stat_modifier' and 'duration_turns'.
    """

    try:
        # ==========================================
        # REAL API CALL GOES HERE:
        # from google import genai
        # client = genai.Client(api_key=api_key)
        # response = client.models.generate_content(model='gemini-2.5-pro', contents=system_prompt)
        # raw_response_text = response.text
        # ==========================================

        # MOCK FALLBACK (If API isn't active)
        raw_response_text = """```json
        {
            "lore": "The Neon Syndicate has finally breached the upper canopy of the Cyber-Jungle. For decades, the Bio-Druids maintained peace, weaving technology into the very roots of the ancient trees. Now, corporate greed seeks to harvest the sap-batteries that power the ecosystem. The war for the canopy begins.",
            "stage": {
                "name": "Smog Canopy", "type": "Stage", "stage_effect": "smog", 
                "desc": "Thick pollution chokes the battlefield. All cards lose 1 DEF per turn.",
                "visuals": {"css_gradient": "linear-gradient(to bottom, #1a2a22, #4a5a42)", "weather_overlay": "rain"}
            },
            "player_cards": [
                {"name": "Bio-Druid Vanguard", "type": "Attack", "atk": 4, "def": 6, "desc": "A frontline defender made of bark and steel."},
                {"name": "Sap-Surge", "type": "Buff", "stat_modifier": {"atk": 3, "def": 1}, "duration_turns": 2, "desc": "Overcharges the circuitry of an ally."}
            ],
            "enemy_cards": [
                {"name": "Syndicate Shredder", "type": "Attack", "atk": 7, "def": 2, "ability": {"name": "Chain-Blade", "trigger": "Active", "effect_type": "status", "status": "bleed", "duration_turns": 2}, "desc": "Glass cannon built to clear the forest."},
                {"name": "EMP Drone", "type": "Attack", "atk": 2, "def": 3, "desc": "Disrupts bio-mechanical signals."}
            ]
        }
        ```"""

        cleaned_text = re.sub(r'```json\n|\n```|```', '', raw_response_text).strip()
        scenario_data = json.loads(cleaned_text)
        return scenario_data

    except Exception as e:
        st.error(f"API Error: {e}")
        return None

def fetch_real_ai_image(prompt: str) -> str:
    """
    Uses Pollinations.ai for instant, free, keyless AI image generation.
    Generates a 256x384 portrait image perfect for trading cards.

    IMPORTANT: return a *direct image URL* (not a markdown link),
    so <img src='...'> works correctly.
    """
    safe_prompt = urllib.parse.quote(prompt + ", beautiful digital art, fantasy trading card illustration, masterpiece")
    seed = random.randint(1, 100000)
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=256&height=384&nologo=true&seed={seed}"

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario:
        return

    st.session_state.lore = scenario.get("lore", "War has broken out.")
    st.session_state.active_stage = scenario.get("stage")

    # Process Player Deck
    p_deck = []
    for i, card in enumerate(scenario.get("player_cards", []) * 4):
        card['id'] = f"p_{i}"
        card['is_flipped'] = False
        card['image'] = fetch_real_ai_image(f"{card['name']}, {theme} protagonist")
        p_deck.append(card.copy())

    random.shuffle(p_deck)
    st.session_state.deck = p_deck
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(4)]

    # Process Enemy Deck
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
    st.session_state.game_active = True

def play_card(card_index, is_player=True):
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck

    card = hand.pop(card_index)
    card['is_flipped'] = False

    board.append(card)
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} played {card['name']}.")
    if deck:
        hand.append(deck.pop())

def _find_player_board_index_by_id(card_id: str):
    for idx, c in enumerate(st.session_state.board):
        if c.get('id') == card_id:
            return idx
    return None

def resolve_attack(attacker_idx: int, target_idx: int):
    """Resolve combat between a specific player attacker and specific enemy target."""
    if attacker_idx is None or target_idx is None:
        return

    # Validate indexes in case the board changed since selection
    if attacker_idx < 0 or attacker_idx >= len(st.session_state.board):
        return
    if target_idx < 0 or target_idx >= len(st.session_state.enemy_board):
        return

    attacker = st.session_state.board[attacker_idx]
    target = st.session_state.enemy_board[target_idx]

    if attacker.get('type') != 'Attack':
        log_event(f"⚠️ {attacker['name']} cannot attack (not an Attack card).")
        return

    atk = int(attacker.get('atk', 0))
    target['def'] = int(target.get('def', 0)) - atk
    log_event(f"🎯 {attacker['name']} hit {target['name']} for {atk} DMG!")

    # Mark attacker as exhausted for this turn
    st.session_state.attacks_used.add(attacker.get('id'))

    if target['def'] <= 0:
        log_event(f"💀 {target['name']} was destroyed!")
        st.session_state.enemy_board.pop(target_idx)


def resolve_direct_attack(attacker_idx: int):
    """Attack the enemy hero directly (only when enemy board is empty)."""
    if attacker_idx is None:
        return
    if attacker_idx < 0 or attacker_idx >= len(st.session_state.board):
        return
    if st.session_state.enemy_board:
        return

    attacker = st.session_state.board[attacker_idx]
    if attacker.get('type') != 'Attack':
        log_event(f"⚠️ {attacker['name']} cannot attack (not an Attack card).")
        return

    atk = int(attacker.get('atk', 0))
    st.session_state.enemy_hp -= atk
    st.session_state.attacks_used.add(attacker.get('id'))
    log_event(f"💥 {attacker['name']} hit the enemy for {atk} DMG!")
    if st.session_state.enemy_hp <= 0:
        st.session_state.enemy_hp = 0
        log_event("🏆 You win!")


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
                    # If the destroyed card was selected as attacker, clear selection
                    if st.session_state.selected_attacker == target.get('id'):
                        st.session_state.selected_attacker = None
                    st.session_state.board.pop(0)
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 {enemy_card['name']} hit YOU for {atk} DMG!")

    st.session_state.turn_count += 1
    log_event("--- Your Turn ---")
    # Reset player attack exhaustion at the start of the player's turn
    st.session_state.attacks_used = set()

def end_turn():
    # Clear any pending attack selection at end of turn
    st.session_state.selected_attacker = None
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_index, location_type, is_enemy=False):
    """
    location_type:
      - hand: player's hand
      - board: player's field
      - eboard: enemy field
    """
    card_key = f"{location_type}_{card['id']}"

    # Toggle flip state
    if st.button("🔄 Flip", key=f"btn_{card_key}"):
        card['is_flipped'] = not card.get('is_flipped', False)
        st.rerun()

    # Determine selection highlight
    is_selected_attacker = (not is_enemy and location_type == 'board' and st.session_state.selected_attacker == card.get('id'))
    border_color = "#ff4a4a" if is_enemy else "#4a8cff"
    highlight = "0 0 0 4px rgba(74,140,255,0.35), 0 0 18px rgba(74,140,255,0.45)" if is_selected_attacker else "0 4px 8px rgba(0,0,0,0.6)"

    # Targeting cues (when an attacker is selected, enemy cards become targetable)
    is_targetable_enemy = (is_enemy and location_type == 'eboard' and st.session_state.selected_attacker is not None)
    target_glow = "0 0 0 4px rgba(255,205,0,0.35), 0 0 18px rgba(255,205,0,0.35)" if is_targetable_enemy else ""

    extra_class = " selected" if is_selected_attacker else ""
    extra_class += " targetable" if is_targetable_enemy else ""

    # CSS for the physical card look
    # IMPORTANT: Streamlit markdown treats lines indented by 4+ spaces as a code block.
    # Dedent HTML before rendering so you don't see literal <div> text.
    card_html = f"""
<div class='card-shell{extra_class}' style='
    background-color: #1e1e1e;
    border: 3px solid {border_color};
    border-radius: 12px;
    box-shadow: {target_glow if (is_targetable_enemy and not is_selected_attacker) else highlight};
    height: 320px;
    overflow: hidden;
    position: relative;
    color: white;
    font-family: sans-serif;
'>
"""

    if not card.get('is_flipped', False):
        # --- FRONT OF CARD ---
        card_html += f"""
<div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%;'>
    <img src='{card.get("image", "")}' style='width: 100%; height: 100%; object-fit: cover; opacity: 0.85;'>
</div>
<div style='position: absolute; bottom: 0; left: 0; width: 100%; background: rgba(0,0,0,0.82); padding: 8px; border-top: 1px solid {border_color};'>
    <h4 style='margin: 0; font-size: 16px; text-align: center;'>{card['name']}</h4>
</div>
"""
    else:
        # --- BACK OF CARD ---
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

        card_html += f"""
    <div style='display: flex; justify-content: space-between; font-weight: bold; font-size: 18px; border-top: 1px solid #444; padding-top: 10px;'>
        <span>⚔️ {atk_val}</span>
        <span>🛡️ {def_val}</span>
    </div>
</div>
"""

    card_html += "</div>"
    st.markdown(textwrap.dedent(card_html).strip(), unsafe_allow_html=True)

    # --- Interactive buttons below the card ---
    # 1) Hand: play card
    if not is_enemy and location_type == 'hand':
        if st.button("Play Card", key=f"play_{card_key}", type="primary", use_container_width=True):
            play_card(location_index, is_player=True)
            st.rerun()

    # 2) Player board: select / cancel attacker
    if not is_enemy and location_type == 'board':
        can_attack = (card.get('type') == 'Attack') and (card.get('id') not in st.session_state.attacks_used)
        if st.session_state.selected_attacker == card.get('id'):
            if st.button("❌ Cancel", key=f"cancel_atk_{card_key}", use_container_width=True):
                st.session_state.selected_attacker = None
                st.rerun()
        else:
            attack_label = "⚔️ Attack" if can_attack else ("⛔ Exhausted" if card.get('type') == 'Attack' else "(No Attack)")
            if st.button(attack_label, key=f"atk_{card_key}", use_container_width=True, disabled=not can_attack):
                st.session_state.selected_attacker = card.get('id')
                log_event(f"🟦 Selected attacker: {card['name']}. Choose a target.")
                st.rerun()

    # 3) Enemy board: target button appears only when an attacker is selected
    if is_enemy and location_type == 'eboard' and st.session_state.selected_attacker:
        attacker_idx = _find_player_board_index_by_id(st.session_state.selected_attacker)
        attacker_valid = attacker_idx is not None and attacker_idx < len(st.session_state.board) and st.session_state.board[attacker_idx].get('type') == 'Attack' and (st.session_state.board[attacker_idx].get('id') not in st.session_state.attacks_used)
        if st.button("🎯 Target", key=f"tgt_{card_key}", type="primary", use_container_width=True, disabled=not attacker_valid):
            if attacker_valid:
                resolve_attack(attacker_idx, location_index)
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
            with st.spinner("Writing lore and generating art (this takes a few seconds)..."):
                setup_game(theme_input)
            st.rerun()

else:
    # --- LORE & SCOREBOARD ---
    with st.expander("📖 Scenario Lore", expanded=False):
        st.write(st.session_state.lore)

    st.write("---")
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        if st.session_state.active_stage:
            st.success(f"**🌍 Active Stage:** {st.session_state.active_stage['name']}")
    with col2:
        st.markdown(f"<h3 style='color:#ff4a4a; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<h3 style='color:#4a8cff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
    with col4:
        if st.button("⏭️ End Turn", use_container_width=True, type="primary"):
            end_turn()
            st.rerun()

    # --- BATTLEFIELD ZONE ---
    st.markdown("""
        <div style='background: rgba(0,0,0,0.5); padding: 20px; border-radius: 15px; border: 1px solid #444; margin-bottom: 20px;'>
    """, unsafe_allow_html=True)

    col_main, col_log = st.columns([4, 1])

    with col_main:
        # Enemy Board
        st.markdown("<h4 style='color:#ff4a4a; text-align:center;'>👿 Enemy Field</h4>", unsafe_allow_html=True)
        if st.session_state.enemy_board:
            eboard_cols = st.columns(max(len(st.session_state.enemy_board), 1))
            for i, card in enumerate(st.session_state.enemy_board):
                with eboard_cols[i]:
                    render_card(card, i, "eboard", is_enemy=True)
        else:
            st.caption("Enemy field is empty.")

            # Optional: allow attacking the enemy hero directly when their field is empty
            if st.session_state.selected_attacker:
                attacker_idx = _find_player_board_index_by_id(st.session_state.selected_attacker)
                attacker_valid = (
                    attacker_idx is not None
                    and attacker_idx < len(st.session_state.board)
                    and st.session_state.board[attacker_idx].get('type') == 'Attack'
                    and (st.session_state.board[attacker_idx].get('id') not in st.session_state.attacks_used)
                )
                if st.button("🎯 Target Enemy", key="tgt_enemy", type="primary", use_container_width=True, disabled=not attacker_valid):
                    if attacker_valid:
                        resolve_direct_attack(attacker_idx)
                    st.session_state.selected_attacker = None
                    st.rerun()

        st.markdown("<hr style='border-color: #555;'>", unsafe_allow_html=True)

        # Player Board
        st.markdown("<h4 style='color:#4a8cff; text-align:center;'>🛡️ Your Field</h4>", unsafe_allow_html=True)
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]:
                    render_card(card, i, "board", is_enemy=False)
        else:
            st.caption("Your field is empty.")

        # Small helper hint
        if st.session_state.selected_attacker:
            st.info("Attacker selected — click 🎯 Target on an enemy card.")

    with col_log:
        st.markdown("<b>📜 Battle Log</b>", unsafe_allow_html=True)
        for log in st.session_state.battle_log:
            st.markdown(
                f"<div style='font-size:12px; margin-bottom:5px; padding:5px; background:rgba(255,255,255,0.05); border-radius:4px;'>{log}</div>",
                unsafe_allow_html=True
            )

    st.markdown("</div>", unsafe_allow_html=True)  # End Battlefield Zone

    # --- HAND ZONE ---
    st.markdown("<h3 style='text-align:center;'>🖐️ Your Hand</h3>", unsafe_allow_html=True)
    if st.session_state.hand:
        hand_cols = st.columns(len(st.session_state.hand))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]:
                render_card(card, i, "hand", is_enemy=False)

    st.write("---")
    if st.button("Surrender & Restart"):
        st.session_state.game_active = False
        st.session_state.selected_attacker = None
        st.session_state.attacks_used = set()
        st.rerun()
