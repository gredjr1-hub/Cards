import streamlit as st
import random
import json
import re
import urllib.parse

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")

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

def log_event(message):
    st.session_state.battle_log.insert(0, message)
    if len(st.session_state.battle_log) > 6:
        st.session_state.battle_log.pop()

# --- Real API Integration ---
def call_llm_api(theme):
    api_key = st.secrets["GEMINI_API_KEY"]
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
        # client = genai.Client(api_key="YOUR_API_KEY")
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

def fetch_real_ai_image(prompt):
    """
    Uses Pollinations.ai for instant, free, keyless AI image generation.
    Generates a 256x384 portrait image perfect for trading cards.
    """
    safe_prompt = urllib.parse.quote(prompt + ", beautiful digital art, fantasy trading card illustration, masterpiece")
    # Adding a random seed ensures we get different images for cards with the same name if needed
    seed = random.randint(1, 100000)
    return f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){safe_prompt}?width=256&height=384&nologo=true&seed={seed}"

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario: return
        
    st.session_state.lore = scenario.get("lore", "War has broken out.")
    st.session_state.active_stage = scenario.get("stage")
    
    # Process Player Deck
    p_deck = []
    # Multiplying by 4 to make a full deck out of the 8 generated unique cards
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
    st.session_state.game_active = True

def play_card(card_index, is_player=True):
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck
    
    card = hand.pop(card_index)
    card['is_flipped'] = False
    
    board.append(card)
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} played {card['name']}.")
        
    if deck: hand.append(deck.pop())

def execute_enemy_turn():
    log_event("--- Enemy Turn ---")
    if st.session_state.enemy_hand and len(st.session_state.enemy_board) < 5:
        play_card(0, is_player=False)
        
    for enemy_card in st.session_state.enemy_board:
        if enemy_card['type'] == 'Attack' and not enemy_card.get('active_status'):
            atk = enemy_card.get('atk', 0)
            if st.session_state.board:
                target = st.session_state.board[0]
                target['def'] = target.get('def', 0) - atk
                log_event(f"⚔️ {enemy_card['name']} hit {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 {target['name']} was destroyed!")
                    st.session_state.board.pop(0)
            else:
                st.session_state.player_hp -= atk
                log_event(f"💥 {enemy_card['name']} hit YOU for {atk} DMG!")

    st.session_state.turn_count += 1
    log_event("--- Your Turn ---")

def end_turn():
    # Process environmental effects here if needed
    execute_enemy_turn()

# --- UI Rendering Helpers ---
def render_card(card, location_index, location_type, is_enemy=False):
    card_key = f"{location_type}_{card['id']}"
    
    # Toggle flip state
    if st.button("🔄 Flip", key=f"btn_{card_key}"):
        card['is_flipped'] = not card.get('is_flipped', False)
        st.rerun()

    border_color = "#ff4a4a" if is_enemy else "#4a8cff"
    
    # CSS for the physical card look
    card_html = f"""
    <div style='
        background-color: #1e1e1e;
        border: 3px solid {border_color};
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.6);
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
            <img src='{card["image"]}' style='width: 100%; height: 100%; object-fit: cover; opacity: 0.8;'>
        </div>
        <div style='position: absolute; bottom: 0; left: 0; width: 100%; background: rgba(0,0,0,0.8); padding: 8px; border-top: 1px solid {border_color};'>
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
            card_html += f"<div style='background: #333; padding: 5px; border-radius: 5px; margin-bottom: 10px;'><b style='font-size: 12px;'>✨ {ab['name']}</b><br><span style='font-size: 11px;'>Trigger: {ab['trigger']}</span></div>"
            
        card_html += f"""
            <div style='display: flex; justify-content: space-between; font-weight: bold; font-size: 18px; border-top: 1px solid #444; padding-top: 10px;'>
                <span>⚔️ {atk_val}</span>
                <span>🛡️ {def_val}</span>
            </div>
        </div>
        """
        
    card_html += "</div>"
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Render interactive buttons below the card
    if not is_enemy and location_type == 'hand':
        if st.button("Play Card", key=f"play_{card_key}", type="primary", use_container_width=True):
            play_card(location_index, is_player=True)
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
        if st.session_state.active_stage: st.success(f"**🌍 Active Stage:** {st.session_state.active_stage['name']}")
    with col2: st.markdown(f"<h3 style='color:#ff4a4a; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3: st.markdown(f"<h3 style='color:#4a8cff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
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
                with eboard_cols[i]: render_card(card, i, "eboard", is_enemy=True)
        else: st.caption("Enemy field is empty.")

        st.markdown("<hr style='border-color: #555;'>", unsafe_allow_html=True)
        
        # Player Board
        st.markdown("<h4 style='color:#4a8cff; text-align:center;'>🛡️ Your Field</h4>", unsafe_allow_html=True)
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]: render_card(card, i, "board", is_enemy=False)
        else: st.caption("Your field is empty.")
    
    with col_log:
        st.markdown("<b>📜 Battle Log</b>", unsafe_allow_html=True)
        for log in st.session_state.battle_log:
            st.markdown(f"<div style='font-size:12px; margin-bottom:5px; padding:5px; background:rgba(255,255,255,0.05); border-radius:4px;'>{log}</div>", unsafe_allow_html=True)
            
    st.markdown("</div>", unsafe_allow_html=True) # End Battlefield Zone

    # --- HAND ZONE ---
    st.markdown("<h3 style='text-align:center;'>🖐️ Your Hand</h3>", unsafe_allow_html=True)
    if st.session_state.hand:
        hand_cols = st.columns(len(st.session_state.hand))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]: render_card(card, i, "hand", is_enemy=False)
            
    st.write("---")
    if st.button("Surrender & Restart"):
        st.session_state.game_active = False
        st.rerun()