import streamlit as st
import random
import json
import re
import urllib.parse
import textwrap

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide", initial_sidebar_state="collapsed")

# --- Global CSS (Animations, Vertical Aspect Ratios, Rarity) ---
st.markdown("""
<style>
/* Enforce strict vertical card dimensions */
.card-shell { 
    aspect-ratio: 2.5 / 3.5; 
    width: 100%; 
    max-width: 240px; 
    margin: 0 auto;
    position: relative; 
    background: linear-gradient(135deg, #2a2a35, #101018); /* Fallback if image fails */
    border-radius: 12px;
    overflow: hidden;
    color: white; 
    font-family: sans-serif;
    transition: transform 150ms ease, box-shadow 150ms ease, filter 150ms ease; 
}

/* Interaction States */
.card-shell:hover { transform: translateY(-4px) scale(1.02); filter: brightness(1.1); }
.card-shell.targetable { cursor: crosshair; }
.card-shell.selected { transform: translateY(-8px) scale(1.03); z-index: 10; }

/* Rarity Borders */
.rarity-Common { border: 3px solid #666666; }
.rarity-Rare { border: 3px solid #0070dd; box-shadow: 0 0 10px rgba(0,112,221,0.5); }
.rarity-Epic { border: 3px solid #a335ee; box-shadow: 0 0 15px rgba(163,53,238,0.6); }
.rarity-Legendary { border: 3px solid #ff8000; box-shadow: 0 0 20px rgba(255,128,0,0.8); }

/* Combat Animations */
@keyframes lungeUp {
    0% { transform: translateY(0); }
    50% { transform: translateY(-30px) scale(1.05); }
    100% { transform: translateY(0); }
}
@keyframes shakeDamage {
    0% { transform: translateX(0); filter: brightness(1); }
    20% { transform: translateX(-10px); filter: brightness(2) hue-rotate(-50deg); }
    40% { transform: translateX(10px); }
    60% { transform: translateX(-10px); }
    80% { transform: translateX(10px); }
    100% { transform: translateX(0); filter: brightness(1); }
}
.anim-attack { animation: lungeUp 0.4s ease forwards; }
.anim-damage { animation: shakeDamage 0.4s ease forwards; }

/* Clean UI tweaks */
.stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
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
    'selected_attacker': None, 
    'selected_buff': None, # New: Tracks a buff card waiting to be applied
    'attacks_used': set(),
    'animation_state': {} # New: Tracks which cards should animate this render
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
    
    Return ONLY a valid JSON object with this exact structure:
    {{
      "lore": "Two paragraphs describing the conflict and factions.",
      "stage": {{"name": "Stage Name", "type": "Stage", "visuals": {{"css_gradient": "linear-gradient(to bottom, #111111, #444444)"}}}},
      "player_cards": [ Generate exactly 6 Attack cards and 2 Buff cards ],
      "enemy_cards": [ Generate exactly 6 Attack cards and 2 Buff cards ]
    }}
    
    Rules for ALL cards:
    - Must include a "rarity" field (choose exactly one: "Common", "Rare", "Epic", "Legendary").
    
    Rules for Attack cards:
    - Must have 'atk' (1-8), 'def' (1-8).
    - Optionally include an 'ability' object: {{"name": "Cleave", "desc": "Deals 2 damage to enemy leader."}}
    
    Rules for Buff cards:
    - Must have 'stat_modifier' object (e.g. {{"atk": 2, "def": 1}}).
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
    """Returns a direct Pollinations URL. Removed backend fetching to prevent bot-blocks."""
    safe_prompt = urllib.parse.quote(prompt + ", trading card art, centered, masterpiece")
    seed = random.randint(1, 100000)
    return f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){safe_prompt}?width=256&height=384&nologo=true&seed={seed}"

# --- Game Logic ---
def setup_game(theme):
    scenario = call_llm_api(theme)
    if not scenario: return

    st.session_state.lore = scenario.get("lore", "War has broken out.")
    st.session_state.active_stage = scenario.get("stage")

    def process_deck(cards, is_player):
        deck = []
        for i, card in enumerate(cards * 4): # Multiply to build a deck
            card['id'] = f"{'p' if is_player else 'e'}_{i}_{random.randint(100,999)}"
            card['is_flipped'] = False
            card['rarity'] = card.get('rarity', 'Common')
            card['ability_used'] = False
            card['image'] = fetch_real_ai_image(f"{card['name']}, {theme}")
            deck.append(card.copy())
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

def play_card(card_index, is_player=True):
    hand = st.session_state.hand if is_player else st.session_state.enemy_hand
    board = st.session_state.board if is_player else st.session_state.enemy_board
    deck = st.session_state.deck if is_player else st.session_state.enemy_deck

    card = hand.pop(card_index)
    card['is_flipped'] = False
    board.append(card)
    log_event(f"🃏 {'Player' if is_player else 'Enemy'} deployed {card['name']}.")
    if deck: hand.append(deck.pop())

def apply_buff(buff_idx, target_idx):
    """Applies a buff card from hand to a friendly card on the board."""
    buff_card = st.session_state.hand.pop(buff_idx)
    target_card = st.session_state.board[target_idx]
    
    mods = buff_card.get('stat_modifier', {})
    atk_mod = mods.get('atk', 0)
    def_mod = mods.get('def', 0)
    
    target_card['atk'] = target_card.get('atk', 0) + atk_mod
    target_card['def'] = target_card.get('def', 0) + def_mod
    
    log_event(f"✨ Applied {buff_card['name']} to {target_card['name']} (+{atk_mod} ATK, +{def_mod} DEF)!")
    
    st.session_state.animation_state = {'type': 'buff', 'target_id': target_card['id']}
    if st.session_state.deck: st.session_state.hand.append(st.session_state.deck.pop())

def trigger_ability(board_idx):
    """Triggers a card's special ability."""
    card = st.session_state.board[board_idx]
    card['ability_used'] = True
    ab_name = card.get('ability', {}).get('name', 'Ability')
    
    # Generic prototype effect: Deals 2 damage directly to enemy leader
    st.session_state.enemy_hp -= 2
    log_event(f"⚡ {card['name']} used {ab_name}! Dealt 2 DMG to Enemy Leader.")
    check_win_condition()

def resolve_attack(attacker_idx: int, target_idx: int):
    attacker = st.session_state.board[attacker_idx]
    target = st.session_state.enemy_board[target_idx]

    atk = int(attacker.get('atk', 0))
    target['def'] = int(target.get('def', 0)) - atk
    log_event(f"🎯 {attacker['name']} hit {target['name']} for {atk} DMG!")
    
    st.session_state.attacks_used.add(attacker.get('id'))
    # Trigger animations for both cards
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id'], 'target_id': target['id']}

    if target['def'] <= 0:
        log_event(f"💀 {target['name']} was destroyed!")
        st.session_state.enemy_board.pop(target_idx)
    
    check_win_condition()

def resolve_direct_attack(attacker_idx: int):
    attacker = st.session_state.board[attacker_idx]
    atk = int(attacker.get('atk', 0))
    st.session_state.enemy_hp -= atk
    st.session_state.attacks_used.add(attacker.get('id'))
    
    st.session_state.animation_state = {'type': 'combat', 'attacker_id': attacker['id']}
    log_event(f"💥 {attacker['name']} hit the enemy leader for {atk} DMG!")
    check_win_condition()

def execute_enemy_turn():
    log_event("--- Enemy Turn ---")
    st.session_state.animation_state = {} # Clear old animations
    
    # Simple AI: Play first Attack card in hand
    if st.session_state.enemy_hand and len(st.session_state.enemy_board) < 5:
        for i, c in enumerate(st.session_state.enemy_hand):
            if c.get('type') == 'Attack':
                play_card(i, is_player=False)
                break

    for enemy_card in list(st.session_state.enemy_board):
        if enemy_card.get('type') == 'Attack':
            atk = int(enemy_card.get('atk', 0))
            if st.session_state.board:
                target = st.session_state.board[0]
                target['def'] = int(target.get('def', 0)) - atk
                log_event(f"⚔️ Enemy {enemy_card['name']} hit {target['name']} for {atk} DMG!")
                if target['def'] <= 0:
                    log_event(f"💀 Your {target['name']} was destroyed!")
                    st.session_state.board.pop(0)
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
def render_card(card, location_index, location_type, is_enemy=False):
    card_key = f"{location_type}_{card['id']}"

    # Determine selection highlights
    is_selected_attacker = (not is_enemy and location_type == 'board' and st.session_state.selected_attacker == card.get('id'))
    is_selected_buff = (not is_enemy and location_type == 'hand' and st.session_state.selected_buff == card.get('id'))
    
    is_targetable_enemy = (is_enemy and location_type == 'eboard' and st.session_state.selected_attacker is not None)
    is_targetable_friendly = (not is_enemy and location_type == 'board' and st.session_state.selected_buff is not None)

    # Base Classes & Rarity
    rarity_class = f"rarity-{card.get('rarity', 'Common')}"
    extra_class = f" {rarity_class}"
    
    if is_selected_attacker or is_selected_buff: extra_class += " selected"
    if is_targetable_enemy or is_targetable_friendly: extra_class += " targetable"

    # Animations
    anim_state = st.session_state.get('animation_state', {})
    if anim_state.get('attacker_id') == card['id']: extra_class += " anim-attack"
    if anim_state.get('target_id') == card['id']: extra_class += " anim-damage"

    # HTML Construction
    card_html = f"<div class='card-shell{extra_class}'>"
    
    if not card.get('is_flipped', False):
        card_html += f"""
        <div style='position: absolute; top: 0; left: 0; width: 100%; height: 100%;'>
            <img src='{card.get("image", "")}' style='width: 100%; height: 100%; object-fit: cover; opacity: 0.9;'>
        </div>
        <div style='position: absolute; bottom: 0; left: 0; width: 100%; background: rgba(0,0,0,0.85); padding: 8px; border-top: 1px solid #444;'>
            <h4 style='margin: 0; font-size: 14px; text-align: center;'>{card['name']}</h4>
        </div>
        """
        # Stats Overlay for Front
        if card.get('type') == 'Attack':
            card_html += f"""
            <div style='position: absolute; bottom: 45px; width: 100%; display: flex; justify-content: space-between; padding: 0 10px; font-weight: bold; font-size: 18px; text-shadow: 2px 2px 4px #000;'>
                <span style='background: rgba(200,0,0,0.8); padding: 2px 8px; border-radius: 5px;'>⚔️ {card.get('atk', 0)}</span>
                <span style='background: rgba(0,100,200,0.8); padding: 2px 8px; border-radius: 5px;'>🛡️ {card.get('def', 0)}</span>
            </div>
            """
    else:
        # Card Back (Details)
        card_html += f"""
        <div style='padding: 15px; height: 100%; display: flex; flex-direction: column; background: rgba(0,0,0,0.8);'>
            <h4 style='margin-top: 0; border-bottom: 1px solid #666; padding-bottom: 5px;'>{card['name']}</h4>
            <p style='font-size: 11px; color: #aaa; margin-bottom: 5px;'>[{card['type']} - {card.get('rarity')}]</p>
            <p style='font-size: 13px; flex-grow: 1; overflow-y: auto;'><i>"{card.get('desc', 'No lore.')}"</i></p>
        """
        if 'ability' in card:
            ab = card['ability']
            card_html += f"<div style='background: #333; padding: 5px; border-radius: 5px; margin-bottom: 10px; font-size: 11px;'><b>✨ {ab.get('name','Ability')}</b><br>{ab.get('desc','')}</div>"
        
        if card.get('type') == 'Attack':
            card_html += f"<div style='display:flex;justify-content:space-between;font-weight:bold;font-size:16px;border-top:1px solid #444;padding-top:10px;'><span>⚔️ {card.get('atk')}</span><span>🛡️ {card.get('def')}</span></div>"
        elif card.get('type') == 'Buff':
            mods = card.get('stat_modifier', {})
            card_html += f"<div style='font-weight:bold;font-size:14px;border-top:1px solid #444;padding-top:10px;'>Buff: +{mods.get('atk',0)} ATK / +{mods.get('def',0)} DEF</div>"
        
        card_html += "</div>"
    
    card_html += "</div>"
    st.markdown(textwrap.dedent(card_html).strip(), unsafe_allow_html=True)

    # --- Interaction Buttons ---
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("🔄", key=f"btn_{card_key}"):
            card['is_flipped'] = not card.get('is_flipped', False); st.rerun()
            
    with c2:
        # 1. HAND INTERACTIONS
        if not is_enemy and location_type == 'hand':
            if card.get('type') == 'Attack':
                if st.button("Play", key=f"play_{card_key}", type="primary"):
                    play_card(location_index, is_player=True); st.rerun()
            elif card.get('type') == 'Buff':
                if is_selected_buff:
                    if st.button("Cancel", key=f"cancel_{card_key}"):
                        st.session_state.selected_buff = None; st.rerun()
                else:
                    if st.button("Use Buff", key=f"use_{card_key}", type="primary"):
                        st.session_state.selected_buff = card.get('id')
                        st.session_state.selected_attacker = None # Clear other selections
                        st.rerun()

        # 2. PLAYER BOARD INTERACTIONS
        elif not is_enemy and location_type == 'board':
            # Target for a Buff
            if is_targetable_friendly:
                if st.button("Apply Buff Here", key=f"apply_{card_key}", type="primary"):
                    # Find the index of the selected buff in hand
                    buff_idx = next((i for i, c in enumerate(st.session_state.hand) if c['id'] == st.session_state.selected_buff), None)
                    if buff_idx is not None: apply_buff(buff_idx, location_index)
                    st.session_state.selected_buff = None
                    st.rerun()
            
            # Attacking
            elif card.get('type') == 'Attack':
                can_attack = card.get('id') not in st.session_state.attacks_used
                if is_selected_attacker:
                    if st.button("Cancel", key=f"cancel_atk_{card_key}"):
                        st.session_state.selected_attacker = None; st.rerun()
                else:
                    if st.button("Attack", key=f"atk_{card_key}", type="primary", disabled=not can_attack):
                        st.session_state.selected_attacker = card.get('id'); st.rerun()
                
                # Use Ability (If applicable)
                if 'ability' in card and not card.get('ability_used', False):
                    if st.button("✨ Ability", key=f"ab_{card_key}"):
                        trigger_ability(location_index); st.rerun()

        # 3. ENEMY BOARD INTERACTIONS
        elif is_enemy and location_type == 'eboard' and st.session_state.selected_attacker:
            attacker_idx = next((i for i, c in enumerate(st.session_state.board) if c['id'] == st.session_state.selected_attacker), None)
            if attacker_idx is not None and st.button("🎯 Strike", key=f"tgt_{card_key}", type="primary"):
                resolve_attack(attacker_idx, location_index)
                st.session_state.selected_attacker = None; st.rerun()

# --- Main UI Rendering ---
if not st.session_state.game_active:
    st.title("🃏 AI Lore Battler")
    st.markdown("Enter a theme to generate decks, lore, and artwork.")
    theme_input = st.text_input("Theme (e.g., 'Old School RuneScape', 'Cyberpunk Pirates'):")
    if st.button("Generate Scenario & Start", type="primary"):
        if theme_input:
            with st.spinner("Forging cards and contacting Pollinations.ai for artwork..."):
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
    # Top Bar
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        if st.session_state.selected_buff: st.info("⬆️ Select a friendly card to buff.")
        elif st.session_state.selected_attacker: st.warning("🎯 Select an enemy target.")
        else: st.success("🟢 Awaiting Orders")
    with col2: st.markdown(f"<h3 style='color:#ff4a4a; text-align:center;'>Enemy HP: {st.session_state.enemy_hp}</h3>", unsafe_allow_html=True)
    with col3: st.markdown(f"<h3 style='color:#4a8cff; text-align:center;'>Your HP: {st.session_state.player_hp}</h3>", unsafe_allow_html=True)
    with col4:
        if st.button("⏭️ End Turn", use_container_width=True, type="primary"):
            end_turn(); st.rerun()

    st.markdown("<div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 15px; border: 1px solid #444; margin-bottom: 20px;'>", unsafe_allow_html=True)
    col_main, col_log = st.columns([4, 1])

    with col_main:
        # ENEMY BOARD
        st.markdown("<h4 style='color:#ff4a4a; text-align:center;'>👿 Enemy Field</h4>", unsafe_allow_html=True)
        if st.session_state.enemy_board:
            eboard_cols = st.columns(max(len(st.session_state.enemy_board), 1))
            for i, card in enumerate(st.session_state.enemy_board):
                with eboard_cols[i]: render_card(card, i, "eboard", is_enemy=True)
        else:
            st.caption("Enemy field is empty.")
            if st.session_state.selected_attacker:
                attacker_idx = next((i for i, c in enumerate(st.session_state.board) if c['id'] == st.session_state.selected_attacker), None)
                if attacker_idx is not None and st.button("🎯 Target Enemy Leader", key="tgt_enemy", type="primary", use_container_width=True):
                    resolve_direct_attack(attacker_idx)
                    st.session_state.selected_attacker = None; st.rerun()

        st.markdown("<hr style='border-color: #555;'>", unsafe_allow_html=True)

        # PLAYER BOARD
        st.markdown("<h4 style='color:#4a8cff; text-align:center;'>🛡️ Your Field</h4>", unsafe_allow_html=True)
        if st.session_state.board:
            board_cols = st.columns(max(len(st.session_state.board), 1))
            for i, card in enumerate(st.session_state.board):
                with board_cols[i]: render_card(card, i, "board", is_enemy=False)
        else:
            st.caption("Your field is empty.")

    # BATTLE LOG
    with col_log:
        st.markdown("<b>📜 Battle Log</b>", unsafe_allow_html=True)
        for log in st.session_state.battle_log: 
            st.markdown(f"<div style='font-size:13px; margin-bottom:6px; padding:6px; background:rgba(255,255,255,0.05); border-radius:6px; border-left: 3px solid #666;'>{log}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True) 

    # HAND
    st.markdown("<h3 style='text-align:center;'>🖐️ Your Hand</h3>", unsafe_allow_html=True)
    if st.session_state.hand:
        hand_cols = st.columns(len(st.session_state.hand))
        for i, card in enumerate(st.session_state.hand):
            with hand_cols[i]: render_card(card, i, "hand", is_enemy=False)

    st.write("---")
    if st.button("Surrender & Restart"):
        for k in state_defaults: st.session_state[k] = state_defaults[k]
        st.rerun()