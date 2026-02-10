import streamlit as st
from backend import get_chatbot_response
from breed_akc import get_breed_display_names, get_normalized_name_from_display

st.markdown(
        """
        <style>
            :root{ --beige: #f7f1e6; }
            html, body, [data-testid='stAppViewContainer'] { background-color: var(--beige) !important; }
            /* Keep Streamlit app elements on top */
            [data-testid='stAppViewContainer'] > div { position: relative; z-index: 1; }
        </style>
        """,
        unsafe_allow_html=True,
)

# Falling dog emojis
st.markdown(
    """
    <style>
      #dogs { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; overflow: hidden; z-index: 0; }
      .dog { position: absolute; font-size: 34px; opacity: 0.28; transform-origin: center; }
      @keyframes dogfall {
        0% { transform: translateY(-25vh) rotate(0deg); opacity: 0; }
        8% { opacity: 0.28; }
        100% { transform: translateY(120vh) rotate(360deg); opacity: 0.28; }
      }
    </style>
    <div id='dogs'></div>
    """,
    unsafe_allow_html=True,
)

# generate the emoji elements with varied positions/durations
dogs_html = ""
positions = [5, 18, 30, 42, 55, 67, 78, 88, 12, 24, 50, 70]
durations = [9, 11, 8, 12, 10, 9.5, 13, 8.5, 10.2, 9.8, 11.3, 8.7]
delays = [0, 1.5, 0.7, 2.2, 0.3, 1.0, 3.1, 0.4, 2.5, 1.1, 0.9, 0.6]
sizes = [28, 34, 30, 36, 32, 26, 38, 30, 33, 29, 31, 35]
for i in range(len(positions)):
    dogs_html += (
        f"<div class='dog' style=\"left:{positions[i]}%; font-size:{sizes[i]}px; animation: dogfall {durations[i]}s linear {delays[i]}s infinite;\">🐶</div>"
    )

if dogs_html:
    st.markdown(f"<div id='dogs'>{dogs_html}</div>", unsafe_allow_html=True)

# Breed selector in sidebar
st.sidebar.title("🐕 Breed Selector")
st.sidebar.markdown("Select a dog breed for more accurate, AKC-based answers")

# Get breed list
try:
    breed_names = get_breed_display_names()
    breed_options = ["None / Auto-detect"] + breed_names
except Exception as e:
    st.sidebar.error(f"Error loading breeds: {e}")
    breed_options = ["None / Auto-detect"]
    breed_names = []

# Breed dropdown
selected_breed_display = st.sidebar.selectbox(
    "Choose a breed:",
    breed_options,
    key="breed_selector"
)

# Convert display name to normalized name if a breed is selected
selected_breed = None
if selected_breed_display and selected_breed_display != "None / Auto-detect":
    selected_breed = get_normalized_name_from_display(selected_breed_display)
    if selected_breed:
        st.sidebar.success(f"Selected: {selected_breed_display}")
    else:
        st.sidebar.warning("Could not find breed mapping")
        selected_breed = None

# 🎨 TODO: Customize your chatbot's appearance!
st.title("Dog Owner Assistant    🐶")
st.markdown("Ask me anything about caring for a dog")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What would you like to know?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get bot response (pass selected breed if any)
    with st.chat_message("assistant"):
        response = get_chatbot_response(prompt, selected_breed=selected_breed)
        st.markdown(response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
