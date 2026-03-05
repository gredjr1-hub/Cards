import streamlit as st
import random
import json
import re

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide")

# --- Initialize Session State ---
if 'deck' not in st.session_state: st.session_state.deck = []
if 'hand' not in st.session_state: st.session_state.hand = []
if 'active_stage' not in st.session_state: st.session_state.active_stage = None
if 'board' not in st.session_state: st.session_state.board = []
if 'image_cache' not in st.session_state: st.session_state.image_cache = {}
if 'generated_types' not in st.session_state: st.session_state.generated_types = {"Attack": False, "Buff": False, "Stage": False}
if 'turn_count' not in st.session_state: st.session_state.turn_count = 1

# --- Real API Integration Blueprint ---
def call_llm_api(theme):
    """
    This is where you plug in your actual API call (OpenAI, Gemini, etc.).
    It includes the safety block to prevent crashes from bad AI formatting.
    """
    system_prompt = f"""
    You are an expert trading card game designer. Generate a set of 10 playing cards based strictly on the theme: {theme}.
    Include Attack, Buff, and Stage cards.
    Respond ONLY with a valid JSON array matching the required schema. Do not include markdown formatting.
    """
    
    try:
        # ==========================================
        # REPLACE THIS BLOCK WITH YOUR REAL API CALL
        # Example using OpenAI:
        # response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_prompt}])
        # raw_response_text = response.choices[0].message.content
        # ==========================================
        
        # MOCK RESPONSE (Simulating an LLM that accidentally added markdown)
        raw_response_text = """```json
        [
            {
                "name": "Neon Ronin", "type": "Attack", "atk": 7, "def": 4,
                "ability": {"name": "Stun Strike", "trigger": "Active", "effect_type": "status", "status": "stun", "duration_turns": 1},
                "desc": "A fierce warrior."
            },
            {
                "name": "EMP Grenade", "type": "Buff", "stat_modifier": {"atk": 0, "def": -2},
                "special_effect": "sleep", "duration_turns": 2, "desc": "Disables enemy systems."
            },
            {
                "name": "Acid Rain District", "type": "Stage", "stage_effect": "acid_rain", 
                "desc": "All Attack cards lose 1 DEF per turn.",
                "visuals": {"css_gradient": "linear-gradient(to bottom, #2E3B32, #1a2a6c)", "weather_overlay": "rain"}
            }
        ]
        ```"""
        
        # 1. Strip out markdown formatting if the AI disobeys instructions
        cleaned_text = re.sub(r'```json\n|\n```|```', '', raw_response_text).strip()
        
        # 2. Safely parse the JSON
        deck_data = json.loads(cleaned_text)
        
        # Ensure it generated a list
        if not isinstance(deck_data, list):
            raise ValueError("AI did not return a JSON array.")
            
        return deck_data * 3 # Multiplying to make a full deck for the prototype

    except json.JSONDecodeError:
        st.error("The AI formatting failed. It didn't return valid JSON. Please try generating again.")
        return []
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

def generate_image(prompt, card_type):
    """Mocks image generation."""
    if not st.session_state.generated_types[card_type]:
        st.session_state.generated_types[card_type] = True
        return f"[https://via.placeholder.com/200/222222/FFFFFF?text=](https://via.placeholder.com/200/222222/FFFFFF?text=){card_type}+Image"
    else:
        colors = {"Attack": "#FF5555", "Buff": "#55FF55", "Stage": "#5555FF"}
        return colors.get(card_type, "#555555")

# --- Game Logic Functions ---
def build_deck(theme):
    raw_cards = call_llm_api(theme)
    if not raw_cards:
        return # Stop if API failed
        
    new_deck = []
    for i, card in enumerate(raw_cards):
        card['id'] = f"{card['name'].replace(' ', '_')}_{i}" 
        card['is_flipped'] = False # Initialize flip state
        
        if card['name'] not in st.session_state.image_cache:
            img_prompt = f"Trading card art: {card['name']}, theme: {theme}"
            st.session_state.image_cache[card['name']] = generate_image(img_prompt, card['type'])
        
        card['image'] = st.session_state.image_cache[card['name']]
        new_deck.append(card.copy())
        
    random.shuffle(new_deck)
    st.session_state.deck = new_deck
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(3)]

def play_card(card_index):
    card = st.session_state.hand.pop(card_index)
    card['is_flipped'] = False # Ensure card is face-up when played
    
    if card['type'] == 'Stage':
        st.session_state.active_stage = card
    else:
        st.session_state.board.append(card)
        
    if st.session_state.deck:
        st.session_state.hand.append(st.session_state.deck.pop())

def trigger_ability(board_index):
    card = st.session_state.board[board_index]
    ability = card.get('ability', {})
    if ability.get('effect_type') == 'status':
        target_idx = (board_index + 1) % len(st.session_state.board)
        if len(st.session_state.board) > 1:
            st.session_state.board[target_idx]['active_status'] = ability['status']
            st.session_state.board[target_idx]['status_duration'] = ability['duration_turns']
    card['ability_used'] = True

def end_turn():
    st.session_state.turn_count += 1
    if st.session_state.active_stage:
        if st.session_state.active_stage.get('stage_effect') == "acid_rain":
            for card in st.session_state.board:
                if card['type'] == 'Attack' and 'def' in card:
                    card['def'] = max(0, card['def'] - 1) 

    for card in st.session_state.board:
        if card.get('status_duration', 0) > 0:
            card['status_duration'] -= 1
            if card['status_duration'] <= 0:
                card['active_status'] = None

# --- Custom Card Rendering Function ---
def render_card(card, location_index, location_type):
    """Renders a card with flip logic."""
    card_key = f"{location_type}_{card['id']}"
    
    # 1. Flip Button (Always visible on top of the card block)
    if st.button("🔄 Flip", key=f"btn_{card_key}"):
        card['is_flipped'] = not card.get('is_flipped', False)
        st.rerun()

    # Container styling based on flipped state
    bg_color = "#333333" if card['is_flipped'] else "transparent"
    st.markdown(f"<div style='background-color: {bg_color}; padding: 10px; border-radius: 10px; min-height: 250px;'>", unsafe_allow_html=True)
    
    st.markdown(f"**{card['name']}**")

    # 2. Render Front OR Back
    if not card.get('is_flipped', False):
        # --- FRONT OF CARD ---
        if card['image'].startswith('http'):
            st.image(card['image'], use_container_width=True)
        else:
            st.markdown(f"<div style='height: 150px; background-color: {card['image']}; border-radius: 5px;'></div>", unsafe_allow_html=True)
        
        # Show basic stats on front
        if 'atk' in card or 'stat_modifier' in card:
            atk_val = card.get('atk', card.get('stat_modifier', {}).get('atk', 0))
            def_val = card.get('def', card.get('stat_modifier', {}).get('def', 0))
            st.write(f"⚔️ {atk_val} | 🛡️ {def_val}")
            
    else:
        # --- BACK OF CARD ---
        st.caption(f"Type: {card['type']}")
        st.write(f"*{card['desc']}*")
        
        if 'atk' in card or 'stat_modifier' in card:
            atk_val = card.get('atk', card.get('stat_modifier', {}).get('atk', 0))
            def_val = card.get('def', card.get('stat_modifier', {}).get('def', 0))
            st.markdown(f"**Stats:** ⚔️ {atk_val} | 🛡️ {def_val}")
            
        if 'ability' in card:
            ab = card['ability']
            st.markdown(f"**Ability:** {ab['name']}")
            st.caption(f"Trigger: {ab['trigger']} | Effect: {ab.get('effect_type', 'special')}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Active Status Overlays (Always visible regardless of flip)
    if card.get('active_status'):
        st.error(f"⚠️ {card['active_status'].upper()} ({card['status_duration']} turns)")
    
    # Action Buttons
    if location_type == 'hand':
        if st.button("Play Card", key=f"play_{card_key}", type="primary"):
            play_card(location_index)
            st.rerun()
            
    elif location_type == 'board':
        if 'ability' in card and card['ability']['trigger'] == 'Active' and not card.get('ability_used', False):
            if st.button("Use Ability", key=f"ab_{card_key}"):
                trigger_ability(location_index)
                st.rerun()

# --- UI Rendering ---

if st.session_state.active_stage:
    visuals = st.session_state.active_stage.get('visuals', {})
    bg_gradient = visuals.get('css_gradient', 'linear-gradient(to bottom, #1E1E1E, #2D2D2D)')
    weather = visuals.get('weather_overlay', 'none')
    custom_css = f"<style>.stApp {{ background: {bg_gradient}; background-attachment: fixed; transition: background 1s ease; }}</style>"
    if weather == 'rain':
        custom_css += """<style>.weather-layer { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 999; background-image: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0.2) 50%, rgba(255,255,255,0)); background-size: 5px 20px; animation: rainDrop 0.5s linear infinite; } @keyframes rainDrop { 0% { background-position: 0px 0px; } 100% { background-position: 20px 100vh; } }</style><div class="weather-layer"></div>"""
    st.markdown(custom_css, unsafe_allow_html=True)

st.title("🃏 AI Theme Battler")

if not st.session_state.deck and not st.session_state.hand:
    theme_input = st.text_input("Enter a Theme (e.g., 'Cyberpunk', 'Candy Land'):")
    if st.button("Generate Deck"):
        if theme_input:
            with st.spinner("Crafting deck..."): build_deck(theme_input)
            st.rerun()

if st.session_state.hand or st.session_state.board:
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.active_stage: st.success(f"**🌍 Stage:** {st.session_state.active_stage['name']} - {st.session_state.active_stage['desc']}")
        else: st.info("🌍 Neutral Ground.")
    with col2:
        st.markdown(f"### Turn: {st.session_state.turn_count}")
        if st.button("⏭️ Next Turn", use_container_width=True):
            end_turn()
            st.rerun()

    st.write("---")
    st.subheader("Field")
    if st.session_state.board:
        board_cols = st.columns(len(st.session_state.board))
        for i, card in enumerate(st.session_state.board):
            with board_cols[i]:
                render_card(card, location_index=i, location_type="board")
    else:
        st.caption("Field is empty.")

    st.write("---")
    st.subheader("Hand")
    hand_cols = st.columns(len(st.session_state.hand))
    for i, card in enumerate(st.session_state.hand):
        with hand_cols[i]:
            render_card(card, location_index=i, location_type="hand")
                
    if st.button("Reset Game", type="primary"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()