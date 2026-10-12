"""Part 2: Secure Streamlit Dashboard UI (app.py)
This UI handles user login, communicates securely with FastAPI using the 
bearer token, and visualizes the compliance metrics with native charts.
"""

import importlib
import requests
import pandas as pd
import logging
from urllib.parse import urlparse

st = importlib.import_module("streamlit")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://fastapi_backend:8000"
SESSION_TIMEOUT_MINUTES = 60

# Configure Streamlit for security
st.set_page_config(
    page_title="Scientific Compliance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None,
    }
)

# Security: Content Security Policy notice
st.markdown("""
<meta http-equiv="X-UA-Compatible" content="ie=edge">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
""", unsafe_allow_html=True)

st.title("🔬 Scientific Compliance Dashboard")

# =====================================================================
# SESSION STATE SECURITY
# =====================================================================

# Session State Initialization with security context
if "token" not in st.session_state:
    st.session_state.token = None
if "team" not in st.session_state:
    st.session_state.team = None
if "username" not in st.session_state:
    st.session_state.username = None
if "login_time" not in st.session_state:
    st.session_state.login_time = None
if "session_id" not in st.session_state:
    import secrets
    st.session_state.session_id = secrets.token_hex(16)

# Check session timeout
if st.session_state.token:
    from datetime import datetime, timedelta
    current_time = datetime.utcnow()
    login_time = st.session_state.login_time
    
    if isinstance(login_time, str):
        login_time = datetime.fromisoformat(login_time)
    
    if (current_time - login_time).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        st.session_state.token = None
        st.session_state.team = None
        st.session_state.username = None
        st.session_state.login_time = None
        st.warning("⏱️ Session expired due to inactivity. Please log in again.")

# =====================================================================
# SECURE AUTHENTICATION BLOCK
# =====================================================================

if not st.session_state.token:
    st.sidebar.subheader("🔐 Team Authentication")
    
    with st.sidebar.form("login_form", clear_on_submit=True):
        username = st.text_input(
            "Username",
            placeholder="Enter your username",
            help="Your scientific team username"
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            help="Your secure password"
        )
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            # Validate input length to prevent abuse
            if not username or not password:
                st.sidebar.error("❌ Username and password are required.")
            elif len(username) < 3 or len(username) > 32:
                st.sidebar.error("❌ Invalid username format.")
            elif len(password) < 8:
                st.sidebar.error("❌ Password must be at least 8 characters.")
            else:
                try:
                    # Attempt login with secure HTTPS (enforced by infrastructure)
                    response = requests.post(
                        f"{API_URL}/token",
                        data={"username": username, "password": password},
                        timeout=10,
                        verify=True,  # Verify SSL certificates in production
                    )
                    
                    if response.status_code == 200:
                        token_data = response.json()
                        st.session_state.token = token_data["access_token"]
                        st.session_state.username = username
                        st.session_state.login_time = str(datetime.utcnow())
                        logger.info(f"User {username} successfully authenticated")
                        st.success("✅ Successfully logged in!")
                        st.rerun()
                    elif response.status_code == 429:
                        st.sidebar.error("⏱️ Too many login attempts. Please try again later.")
                        logger.warning(f"Rate limit exceeded for user: {username}")
                    else:
                        st.sidebar.error("❌ Invalid credentials or server error.")
                        logger.warning(f"Failed login attempt for user: {username}")
                        
                except requests.exceptions.Timeout:
                    st.sidebar.error("⏳ Connection timeout. Backend API is slow or unreachable.")
                    logger.error("Backend API timeout")
                except requests.exceptions.ConnectionError:
                    st.sidebar.error("🔌 Backend API is unreachable. Please check your connection.")
                    logger.error("Backend API connection error")
                except Exception as e:
                    st.sidebar.error(f"❌ An error occurred: {str(e)}")
                    logger.error(f"Unexpected login error: {str(e)}")
else:
    # User is authenticated
    st.sidebar.success(f"✅ Authenticated: **{st.session_state.username}**")
    st.sidebar.markdown(f"Session ID: `{st.session_state.session_id[:8]}...`")
    st.sidebar.markdown(f"Team: **{st.session_state.team}**")
    
    if st.sidebar.button("🚪 Logout", key="logout_btn"):
        # Secure logout: clear all session state
        st.session_state.token = None
        st.session_state.team = None
        st.session_state.username = None
        st.session_state.login_time = None
        logger.info(f"User {st.session_state.username} logged out")
        st.success("✅ Logged out successfully.")
        st.rerun()

# =====================================================================
# MAIN DASHBOARD CONTENT (Protected UI view)
# =====================================================================

if st.session_state.token:
    try:
        # Prepare secure request headers
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # Fetch compliance audits with timeout
        response = requests.get(
            f"{API_URL}/compliance/audits",
            headers=headers,
            timeout=10,
            verify=True,
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.team = data["team"]
            audits = data["audits"]
            
            st.subheader(f"📊 Compliance Metrics for Team: **{st.session_state.team}**")
            
            if audits:
                df = pd.DataFrame(audits)
                
                # ===== KPI CARDS =====
                col1, col2, col3 = st.columns(3)
                col1.metric("📋 Total Audits Run", len(df))
                col2.metric("📈 Average Score", f"{df['score'].mean():.1f}%")
                col3.metric("✅ Passed Audits", len(df[df['status'] == 'Passed']))
                
                # ===== VISUALIZATION =====
                st.write("---")
                chart_col, table_col = st.columns([2, 1])
                
                with chart_col:
                    st.markdown("### 📉 Performance By Metric")
                    try:
                        # Safely render chart
                        st.bar_chart(
                            data=df.set_index("metric")["score"],
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Unable to render chart: {str(e)}")
                        logger.error(f"Chart rendering error: {str(e)}")
                    
                with table_col:
                    st.markdown("### 📋 Raw Audit Log")
                    display_df = df[["date", "metric", "score", "status"]].copy()
                    # Remove any potentially sensitive columns before display
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # ===== COMPLIANCE SUMMARY =====
                st.write("---")
                st.markdown("### 🎯 Compliance Summary")
                
                passed_count = len(df[df['status'] == 'Passed'])
                failed_count = len(df[df['status'] == 'Failed'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Passed", passed_count, delta=f"{int((passed_count/len(df)*100))}%")
                with col2:
                    st.metric("Failed", failed_count, delta=f"-{int((failed_count/len(df)*100))}%")
            else:
                st.info("ℹ️ No compliance records found for this team.")
                
        elif response.status_code == 401:
            st.error("🔒 Session expired or unauthorized. Please re-authenticate.")
            st.session_state.token = None
            logger.warning("Unauthorized access attempt")
            
        elif response.status_code == 429:
            st.warning("⏱️ Too many requests. Please try again in a moment.")
            logger.warning(f"Rate limit exceeded for user: {st.session_state.username}")
            
        else:
            st.error(f"❌ Error retrieving data (Status: {response.status_code})")
            logger.error(f"API error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        st.error("⏳ Connection timeout. Backend API is unreachable or slow.")
        logger.error("Backend API timeout")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to backend API. Please check your connection.")
        logger.error("Backend API connection error")
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}")
else:
    st.warning("🔐 Please enter your scientific credentials in the sidebar to view compliance data.")
