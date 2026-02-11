"""
Streamlit Web Interface for ISO 15118 + PQC EV Charging System
==============================================================

This web interface allows you to:
1. Start/stop the Cloud Backend, Charging Station, and EV Vehicle
2. Monitor real-time terminal output for all components
3. View system status and performance metrics
4. Configure PQC settings
"""

import streamlit as st
import subprocess
import threading
import queue
import time
import signal
import os
from datetime import datetime
import re
import random

# Detect Streamlit Cloud or demo mode
DEMO_MODE = os.getenv('STREAMLIT_CLOUD', 'false').lower() == 'true' or not os.path.exists('main.py')

# Page configuration
st.set_page_config(
    page_title="ISO 15118 + PQC Control Panel",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'processes' not in st.session_state:
    st.session_state.processes = {
        'cloud': None,
        'station': None,
        'vehicle': None
    }

if 'output_queues' not in st.session_state:
    st.session_state.output_queues = {
        'cloud': queue.Queue(),
        'station': queue.Queue(),
        'vehicle': queue.Queue()
    }

if 'output_logs' not in st.session_state:
    st.session_state.output_logs = {
        'cloud': [],
        'station': [],
        'vehicle': []
    }

if 'metrics' not in st.session_state:
    st.session_state.metrics = {
        'session_time': None,
        'tls_handshake': None,
        'pqc_sign': None,
        'pqc_verify': None,
        'cloud_verify': None
    }

# Helper function to read process output
def enqueue_output(pipe, queue_obj, component):
    """Read output from subprocess and put it in queue"""
    try:
        for line in iter(pipe.readline, ''):
            if line:
                queue_obj.put(line)
                # Extract metrics from output
                if 'TOTAL SESSION TIME:' in line:
                    match = re.search(r'(\d+\.?\d*)\s*ms', line)
                    if match:
                        st.session_state.metrics['session_time'] = match.group(1)
                elif 'TLS Handshake:' in line:
                    match = re.search(r'(\d+\.?\d*)\s*ms', line)
                    if match:
                        st.session_state.metrics['tls_handshake'] = match.group(1)
    except Exception as e:
        queue_obj.put(f"[ERROR] Reading output: {str(e)}\n")
    finally:
        pipe.close()

def start_component(component, host, port, cloud_host=None, cloud_port=None, pqc=False):
    """Start a component (cloud, station, or vehicle)"""
    
    # DEMO MODE: Simulate component startup
    if DEMO_MODE:
        return start_component_demo(component, host, port, cloud_host, cloud_port, pqc)
    
    # Check if already running
    if st.session_state.processes[component] is not None:
        try:
            if st.session_state.processes[component].poll() is None:
                return False, "Component is already running"
        except:
            pass
    
    # Build command
    python_path = os.path.join(os.getcwd(), 'niso', 'bin', 'python')
    if not os.path.exists(python_path):
        python_path = 'python'
    
    cmd = [python_path, 'main.py', '--mode', component, '--host', host, '--port', str(port)]
    
    if component == 'station' and cloud_host and cloud_port:
        cmd.extend(['--cloud-host', cloud_host, '--cloud-port', str(cloud_port)])
    
    if pqc and component in ['station', 'vehicle']:
        cmd.append('--pqc')
    
    # Start process
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        st.session_state.processes[component] = process
        
        # Start output reading thread
        thread = threading.Thread(
            target=enqueue_output,
            args=(process.stdout, st.session_state.output_queues[component], component),
            daemon=True
        )
        thread.start()
        
        return True, f"Started {component} on {host}:{port}"
    
    except Exception as e:
    # DEMO MODE: Simulate component stop
    if DEMO_MODE:
        if st.session_state.processes[component] is not None:
            st.session_state.processes[component] = None
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            st.session_state.output_logs[component].append(f"[{timestamp}] [DEMO] {component.title()} stopped")
            return True, f"[DEMO] Stopped {component}"
        else:
            return False, f"{component} is not running"
    
        return False, f"Error starting {component}: {str(e)}"

def start_component_demo(component, host, port, cloud_host=None, cloud_port=None, pqc=False):
    """Demo mode: Simulate component startup with pre-recorded logs"""
    
    # Mark as "running" in demo mode
    st.session_state.processes[component] = "DEMO_RUNNING"
    
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    
    # Generate demo logs based on component
    if component == 'cloud':
        demo_logs = [
            f"[{timestamp}] Cloud backend starting...",
            f"[{timestamp}] Loading PQC algorithms (Falcon-512, Kyber512)",
            f"[{timestamp}] WebSocket server initialized",
            f"[{timestamp}] Cloud backend listening on {host}:{port}",
            f"[{timestamp}] Ready to accept connections",
            f"[{timestamp}] Certificate verification service active"
        ]
    elif component == 'station':
        demo_logs = [
            f"[{timestamp}] Charging Station (SECC) starting...",
            f"[{timestamp}] Loading PQC keys (Falcon-512)" if pqc else f"[{timestamp}] Loading classical keys",
            f"[{timestamp}] Connecting to cloud backend at ws://{cloud_host}:{cloud_port}",
            f"[{timestamp}] ✓ Connected to cloud backend",
            f"[{timestamp}] TLS server initialized",
            f"[{timestamp}] Station listening on {host}:{port}",
            f"[{timestamp}] Ready for vehicle connections",
            f"[{timestamp}] PQC Mode: ENABLED" if pqc else f"[{timestamp}] PQC Mode: DISABLED"
        ]
    else:  # vehicle
        demo_logs = [
            f"[{timestamp}] Electric Vehicle (EVCC) starting...",
            f"[{timestamp}] Connecting to charging station at {host}:{port}",
            f"[{timestamp}] TLS handshake initiated",
            f"[{timestamp}] TLS handshake complete (12 ms)",
            f"[{timestamp}] Negotiated cipher: TLS_AES_256_GCM_SHA384",
            f"[{timestamp}] Phase 1: Sending SupportedAppProtocolReq",
            f"[{timestamp}] Phase 1: ACCEPTED ✓ (2 ms)",
            f"[{timestamp}] Phase 2: Proposing PQC algorithms (Falcon-512, Kyber512)" if pqc else f"[{timestamp}] Phase 2: Using classical algorithms",
            f"[{timestamp}] Phase 2: PQC_ONLY mode selected ✓ (6 ms)" if pqc else f"[{timestamp}] Phase 2: CLASSICAL mode ✓ (5 ms)",
            f"[{timestamp}] Phase 3: Sending certificate with Falcon-512 signature" if pqc else f"[{timestamp}] Phase 3: Sending certificate",
            f"[{timestamp}] Phase 3: Certificate VERIFIED ✓ (1 ms)",
            f"[{timestamp}] Phase 4: Requesting authorization",
            f"[{timestamp}] Phase 4: AUTHORIZED ✓ (1 ms)",
            f"[{timestamp}] Phase 5: Charging started",
            f"[{timestamp}] Phase 5: Charging... (500 ms simulation)",
            f"[{timestamp}] Phase 5: Charging complete ✓ (503 ms)",
            f"[{timestamp}] Phase 5: Sending SessionStopReq",
            f"[{timestamp}] Phase 5: Session stopped ✓",
            f"[{timestamp}] ",
            f"[{timestamp}] ✅ CHARGING SESSION COMPLETE",
            f"[{timestamp}] TOTAL SESSION TIME: {random.randint(550, 590)} ms",
            f"[{timestamp}] ",
            f"[{timestamp}] Performance Breakdown:",
            f"[{timestamp}]   - TLS Handshake: 12 ms",
            f"[{timestamp}]   - Protocol Negotiation: 2 ms",
            f"[{timestamp}]   - Algorithm Negotiation: 6 ms",
            f"[{timestamp}]   - Certificate Exchange: 1 ms",
            f"[{timestamp}]   - Authorization: 1 ms",
            f"[{timestamp}]   - Charging: 503 ms",
            f"[{timestamp}]   - Session Stop: 45 ms"
        ]
        
        # Update metrics for demo
        st.session_state.metrics['session_time'] = str(random.randint(550, 590))
        st.session_state.metrics['tls_handshake'] = "12"
        st.session_state.metrics['pqc_sign'] = "8"
        st.session_state.metrics['pqc_verify'] = "3"
        st.session_state.metrics['cloud_verify'] = "6"
    
    # Add logs to session state
    st.session_state.output_logs[component].extend(demo_logs)
    
    return True, f"[DEMO] Started {component} on {host}:{port}"

def stop_component(component):
    """Stop a component"""
    if st.session_state.processes[component] is not None:
        try:
            process = st.session_state.processes[component]
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            
        # DEMO MODE: Simple check
        if DEMO_MODE:
            return "🟢 Running (Demo)"
        
            st.session_state.processes[component] = None
            return True, f"Stopped {component}"
        except Exception as e:
            return False, f"Error stopping {component}: {str(e)}"
    else:
        return False, f"{component} is not running"

def # Skip in demo mode (logs are added directly)
    if DEMO_MODE:
        return
    
    get_component_status(component):
    """Check if component is running"""
    if st.session_state.processes[component] is not None:
        try:
            if st.session_state.processes[component].poll() is None:
                return "🟢 Running"
            else:
                return "🔴 Stopped"
        except:
            return "🔴 Stopped"
    return "🔴 Stopped"

def update_output_logs():
    """Update output logs from queues"""
    for component in ['cloud', 'station', 'vehicle']:
        while True:
            try:
                line = st.session_state.output_queues[component].get_nowait()
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                st.session_state.output_logs[component].append(f"[{timestamp}] {line.strip()}")
                
                # Keep only last 200 lines
                if len(st.session_state.output_logs[component]) > 200:
                    st.session_state.output_logs[component] = st.session_state.output_logs[component][-200:]
            except queue.Empty:
                break

# Main UI
st.title("🔋 ISO 15118 + PQC EV Charging Control Panel")
st.markdown("### Quantum-Safe Electric Vehicle Charging Communication System")

# Show demo mode banner
if DEMO_MODE:
    st.warning("🎭 **DEMO MODE** - Running in simulation mode. Backend services are simulated for demonstration purposes.")
    st.info("💡 For full functionality with real backend services, deploy using Docker or run locally.")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

with st.sidebar:
    st.subheader("Cloud Backend")
    cloud_host = st.text_input("Cloud Host", value="0.0.0.0", key="cloud_host")
    cloud_port = st.number_input("Cloud Port", value=9000, min_value=1024, max_value=65535, key="cloud_port")
    
    st.markdown("---")
    
    st.subheader("Charging Station (SECC)")
    station_host = st.text_input("Station Host", value="0.0.0.0", key="station_host")
    station_port = st.number_input("Station Port", value=15118, min_value=1024, max_value=65535, key="station_port")
    station_cloud_host = st.text_input("Connect to Cloud at", value="localhost", key="station_cloud_host")
    station_cloud_port = st.number_input("Cloud Port (Station)", value=9000, min_value=1024, max_value=65535, key="station_cloud_port")
    
    st.markdown("---")
    
    st.subheader("Electric Vehicle (EVCC)")
    vehicle_host = st.text_input("Connect to Station at", value="localhost", key="vehicle_host")
    vehicle_port = st.number_input("Station Port (Vehicle)", value=15118, min_value=1024, max_value=65535, key="vehicle_port")
    
    st.markdown("---")
    
    st.subheader("Security Settings")
    enable_pqc = st.checkbox("Enable PQC (Falcon-512)", value=True, key="enable_pqc")
    
    if enable_pqc:
        st.info("✅ Quantum-Safe Signatures")
    else:
        st.warning("⚠️ Classical Signatures Only")

# Status Overview
st.header("📊 System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Cloud Backend", get_component_status('cloud'))
with col2:
    st.metric("Charging Station", get_component_status('station'))
with col3:
    st.metric("Electric Vehicle", get_component_status('vehicle'))

# Control Buttons
st.header("🎮 Control Panel")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🚀 Start All", use_container_width=True):
        results = []
        
        # Start cloud
        success, msg = start_component('cloud', cloud_host, cloud_port)
        results.append(msg)
        time.sleep(1)
        
        # Start station
        success, msg = start_component('station', station_host, station_port, 
                                      station_cloud_host, station_cloud_port, enable_pqc)
        results.append(msg)
        time.sleep(1)
        
        # Start vehicle (not automatically)
        # results.append("Vehicle ready to start manually")
        
        for msg in results:
            st.success(msg)

with col2:
    if st.button("⏹️ Stop All", use_container_width=True):
        results = []
        for component in ['vehicle', 'station', 'cloud']:
            success, msg = stop_component(component)
            results.append(msg)
        
        for msg in results:
            st.info(msg)

with col3:
    if st.button("🔄 Restart All", use_container_width=True):
        # Stop all
        for component in ['vehicle', 'station', 'cloud']:
            stop_component(component)
        
        time.sleep(1)
        
        # Start all
        start_component('cloud', cloud_host, cloud_port)
        time.sleep(1)
        start_component('station', station_host, station_port, 
                       station_cloud_host, station_cloud_port, enable_pqc)
        
        st.success("System restarted")

with col4:
    if st.button("🧹 Clear Logs", use_container_width=True):
        for component in ['cloud', 'station', 'vehicle']:
            st.session_state.output_logs[component] = []
        st.success("Logs cleared")

# Individual Component Controls
st.header("🔧 Individual Components")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("☁️ Cloud Backend")
    if st.button("Start Cloud", use_container_width=True, key="start_cloud"):
        success, msg = start_component('cloud', cloud_host, cloud_port)
        if success:
            st.success(msg)
        else:
            st.error(msg)
    
    if st.button("Stop Cloud", use_container_width=True, key="stop_cloud"):
        success, msg = stop_component('cloud')
        if success:
            st.info(msg)
        else:
            st.warning(msg)

with col2:
    st.subheader("🔌 Charging Station")
    if st.button("Start Station", use_container_width=True, key="start_station"):
        success, msg = start_component('station', station_host, station_port,
                                      station_cloud_host, station_cloud_port, enable_pqc)
        if success:
            st.success(msg)
        else:
            st.error(msg)
    
    if st.button("Stop Station", use_container_width=True, key="stop_station"):
        success, msg = stop_component('station')
        if success:
            st.info(msg)
        else:
            st.warning(msg)

with col3:
    st.subheader("🚗 Electric Vehicle")
    if st.button("Start Vehicle", use_container_width=True, key="start_vehicle"):
        success, msg = start_component('vehicle', vehicle_host, vehicle_port, pqc=enable_pqc)
        if success:
            st.success(msg)
        else:
            st.error(msg)
    
    if st.button("Stop Vehicle", use_container_width=True, key="stop_vehicle"):
        success, msg = stop_component('vehicle')
        if success:
            st.info(msg)
        else:
            st.warning(msg)

# Performance Metrics
if st.session_state.metrics['session_time']:
    st.header("⚡ Performance Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Session", 
                 f"{st.session_state.metrics['session_time']} ms" if st.session_state.metrics['session_time'] else "N/A")
    with col2:
        st.metric("TLS Handshake", 
                 f"{st.session_state.metrics['tls_handshake']} ms" if st.session_state.metrics['tls_handshake'] else "N/A")
    with col3:
        st.metric("PQC Sign", 
                 f"{st.session_state.metrics['pqc_sign']} ms" if st.session_state.metrics['pqc_sign'] else "~8 ms")
    with col4:
        st.metric("PQC Verify", 
                 f"{st.session_state.metrics['pqc_verify']} ms" if st.session_state.metrics['pqc_verify'] else "~3 ms")
    with col5:
        st.metric("Cloud Verify", 
                 f"{st.session_state.metrics['cloud_verify']} ms" if st.session_state.metrics['cloud_verify'] else "~6 ms")

# Terminal Output
st.header("🖥️ Terminal Output")

# Update logs from queues
update_output_logs()

# Create tabs for each component
tab1, tab2, tab3 = st.tabs(["☁️ Cloud Backend", "🔌 Charging Station", "🚗 Electric Vehicle"])

with tab1:
    st.subheader("Cloud Backend Output")
    if st.session_state.output_logs['cloud']:
        log_text = "\n".join(st.session_state.output_logs['cloud'][-50:])  # Last 50 lines
        st.code(log_text, language="log")
    else:
        st.info("No output yet. Start the Cloud Backend to see logs.")

with tab2:
    st.subheader("Charging Station Output")
    if st.session_state.output_logs['station']:
        log_text = "\n".join(st.session_state.output_logs['station'][-50:])
        st.code(log_text, language="log")
    else:
        st.info("No output yet. Start the Charging Station to see logs.")

with tab3:
    st.subheader("Electric Vehicle Output")
    if st.session_state.output_logs['vehicle']:
        log_text = "\n".join(st.session_state.output_logs['vehicle'][-50:])
    if DEMO_MODE:
        st.info("💡 Demo Mode: Click buttons to see simulated output. No real processes are started.")
    else:
        st.info("💡 Tip: This page auto-refreshes to show live terminal output. Start the components and watch the logs!")
with col2:
    auto_refresh = st.checkbox("Auto Refresh", value=not DEMO_MODE)  # Disabled by default in demo mode

if auto_refresh and not DEMO_MODE
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.info("💡 Tip: This page auto-refreshes to show live terminal output. Start the components and watch the logs!")
with col2:
    auto_refresh = st.checkbox("Auto Refresh", value=True)

if auto_refresh:
    time.sleep(1)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p><strong>ISO 15118 + Post-Quantum Cryptography System</strong></p>
    <p>Quantum-Safe Electric Vehicle Charging Communication • Falcon-512 Signatures • TLS 1.3</p>
</div>
""", unsafe_allow_html=True)
