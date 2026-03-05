import streamlit as st
import random
import json

# --- Page Config ---
st.set_page_config(page_title="AI Card Battler", layout="wide")

# --- Initialize Session State ---
if 'deck' not in st.session_state:
    st.session_state.deck = []
if 'hand' not in st.session_state:
    st.session_state.hand = []
if 'active_stage' not in st.session_state:
    st.session_state.active_stage = None
if 'board' not in st.session_state:
    st.session_state.board = []
if 'image_cache' not in st.session_state:
    # Caches images by card name to avoid regenerating
    st.session_state.image_cache = {}
if 'generated_types' not in st.session_state:
    # Tracks if we've generated a real image for a specific card type yet
    st.session_state.generated_types = {"Attack": False, "Buff": False, "Stage": False}

# --- AI Mock Functions ---
# Replace these with actual API calls (OpenAI, Gemini, Stability, etc.)
def generate_deck_from_llm(theme):
    """Mocks an LLM returning a JSON array of thematic cards."""
    # In reality, prompt the LLM to return exactly this JSON structure based on the theme.
    mock_response = [
        {"name": f"{theme} Warrior", "type": "Attack", "atk": 5, "def": 4, "desc": "A basic fighter."},
        {"name": f"{theme} Behemoth", "type": "Attack", "atk": 8, "def": 2, "desc": "Hits hard, falls fast."},
        {"name": f"Aura of {theme}", "type": "Buff", "atk": 2, "def": 2, "desc": "Empowers your active fighters."},
        {"name": f"{theme} Wasteland", "type": "Stage", "desc": "Changes the battlefield to a harsh environment.", "bg_color": "#2F4F4F"}
    ]
    # Multiply to create a full deck
    return mock_response * 5 

def generate_image(prompt, card_type):
    """Mocks an image generation API. Returns a URL or placeholder."""
    # Logic: Only generate 1 REAL image per type for the prototype.
    if not st.session_state.generated_types[card_type]:
        st.session_state.generated_types[card_type] = True
        # Return a placeholder image URL to represent a "real" generated image
        return f"https://via.placeholder.com/150/0000FF/FFFFFF?text=Generated+{card_type}"
    else:
        # Return a simple colored box placeholder for the rest
        colors = {"Attack": "#FF9999", "Buff": "#99FF99", "Stage": "#9999FF"}
        return colors.get(card_type, "#CCCCCC")

# --- Game Logic Functions ---
def build_deck(theme):
    raw_cards = generate_deck_from_llm(theme)
    new_deck = []
    for card in raw_cards:
        # Check cache first
        if card['name'] not in st.session_state.image_cache:
            img_prompt = f"A trading card illustration of {card['name']}, theme: {theme}"
            img_data = generate_image(img_prompt, card['type'])
            st.session_state.image_cache[card['name']] = img_data
        
        # Attach cached image data to the card instance
        card['image'] = st.session_state.image_cache[card['name']]
        new_deck.append(card.copy())
        
    random.shuffle(new_deck)
    st.session_state.deck = new_deck
    
    # Draw initial hand
    st.session_state.hand = [st.session_state.deck.pop() for _ in range(3)]

def play_card(card_index):
    card = st.session_state.hand.pop(card_index)
    
    if card['type'] == 'Stage':
        st.session_state.active_stage = card
    else:
        st.session_state.board.append(card)
        
    # Draw a new card to replace it if deck isn't empty
    if st.session_state.deck:
        st.session_state.hand.append(st.session_state.deck.pop())

# --- UI Rendering ---

# 1. Dynamic Background based on Stage Card
if st.session_state.active_stage:
    bg_color = st.session_state.active_stage.get('bg_color', '#1E1E1E')
    # Inject CSS to change the background
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: {bg_color};
            transition: background-color 0.5s ease;
        }}
        </style>
    """, unsafe_allow_html=True)

st.title("🃏 AI Theme Battler")

# 2. Setup Phase
if not st.session_state.deck and not st.session_state.hand:
    theme_input = st.text_input("Enter a Theme to generate your deck (e.g., 'Cyberpunk Samurai', 'Candy Land'):")
    if st.button("Generate Deck"):
        if theme_input:
            with st.spinner("AI is crafting your deck..."):
                build_deck(theme_input)
            st.rerun()

# 3. Game Phase
if st.session_state.hand or st.session_state.board:
    
    # Display Active Stage
    if st.session_state.active_stage:
        st.success(f"**Active Stage:** {st.session_state.active_stage['name']} - {st.session_state.active_stage['desc']}")
    else:
        st.info("No Active Stage. Neutral Ground.")

    st.write("---")
    
    # Display Board
    st.subheader("Your Board")
    if st.session_state.board:
        board_cols = st.columns(len(st.session_state.board))
        for i, card in enumerate(st.session_state.board):
            with board_cols[i]:
                st.markdown(f"**{card['name']}**")
                if card['image'].startswith('http'):
                    st.image(card['image'], use_container_width=True)
                else:
                    st.markdown(f"<div style='height: 150px; background-color: {card['image']}; border-radius: 10px;'></div>", unsafe_allow_html=True)
                if card['type'] == 'Attack':
                    st.write(f"⚔️ {card['atk']} | 🛡️ {card['def']}")
    else:
        st.write("Board is empty.")

    st.write("---")
    
    # Display Hand
    st.subheader("Your Hand")
    hand_cols = st.columns(len(st.session_state.hand))
    for i, card in enumerate(st.session_state.hand):
        with hand_cols[i]:
            st.markdown(f"**{card['name']}** ({card['type']})")
            
            # Render image or placeholder color
            if card['image'].startswith('http'):
                st.image(card['image'], use_container_width=True)
            else:
                st.markdown(f"<div style='height: 150px; background-color: {card['image']}; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: black;'>Placeholder</div>", unsafe_allow_html=True)
            
            st.caption(card['desc'])
            if card['type'] == 'Attack' or card['type'] == 'Buff':
                 st.write(f"⚔️ {card.get('atk', 0)} | 🛡️ {card.get('def', 0)}")
                 
            if st.button(f"Play Card", key=f"play_{i}"):
                play_card(i)
                st.rerun()
                
    st.write(f"**Cards left in deck:** {len(st.session_state.deck)}")
    
    if st.button("Reset Game"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()