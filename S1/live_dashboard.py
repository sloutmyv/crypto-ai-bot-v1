import streamlit as st
import pandas as pd
from binance.streams import ThreadedWebsocketManager # Pour python-binance 1.0.16
import queue
import threading
import time
from datetime import datetime, timezone
import logging

# --- Configuration du Logging ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'
)

# --- Configuration Globale ---
MAX_KLINES_IN_CHART = 100
DATA_FETCH_INTERVAL_SECONDS = 0.5

# --- Fonctions Utilitaires ---
def format_kline_data(kline_msg_data):
    k = kline_msg_data['k']
    return {
        'time': pd.to_datetime(k['t'], unit='ms', utc=True),
        'open': float(k['o']),
        'high': float(k['h']),
        'low': float(k['l']),
        'close': float(k['c']),
        'volume': float(k['v']),
        'close_time': pd.to_datetime(k['T'], unit='ms', utc=True),
        'is_closed': k['x']
    }

# --- Gestionnaire WebSocket et États Globaux ---
data_queue = queue.Queue()

logging.info("Global Scope: Initializing TWM object for python-binance 1.0.16")
twm = ThreadedWebsocketManager()
twm_globally_started_flag = False # Drapeau Python simple pour suivre l'état de twm.start()

current_stream_name_active = None 
websocket_data_flow_active = threading.Event() 

def ensure_twm_globally_started():
    """S'assure que twm.start() a été appelé une fois avec succès."""
    global twm, twm_globally_started_flag
    if not twm_globally_started_flag:
        logging.info("ensure_twm_globally_started: TWM global manager not started yet. Calling twm.start()...")
        try:
            twm.start()
            twm_globally_started_flag = True
            logging.info("ensure_twm_globally_started: TWM global manager started successfully.")
            return True
        except RuntimeError as e:
            if "There is no current event loop" in str(e):
                logging.error(f"ensure_twm_globally_started: RuntimeError: No current event loop during twm.start(). Error: {e}", exc_info=True)
                st.error(f"Erreur asyncio critique: {e}. Le démarrage du WebSocket a échoué.")
            else:
                logging.error(f"ensure_twm_globally_started: Generic RuntimeError during twm.start(): {e}", exc_info=True)
                st.error(f"Erreur Runtime critique au démarrage du TWM: {e}")
            return False
        except Exception as e:
            logging.error(f"ensure_twm_globally_started: Failed to start TWM global manager: {e}", exc_info=True)
            st.error(f"Erreur critique: Impossible de démarrer le gestionnaire WebSocket principal: {e}")
            return False
    # else:
        # logging.debug("ensure_twm_globally_started: TWM global manager already started.")
    return True


def handle_kline_message(msg):
    logging.debug(f"handle_kline_message received msg. Stream active flag: {websocket_data_flow_active.is_set()}")
    data_payload = msg.get('data', msg) 
    if data_payload.get('e') == 'kline':
        k_data = data_payload.get('k')
        if k_data and k_data.get('x'): 
            logging.info(f"Closed kline received for {k_data.get('s')}")
            kline_data_formatted = format_kline_data(data_payload)
            data_queue.put(kline_data_formatted)
    elif 'result' in msg and msg['result'] is None:
        logging.info(f"Control message from WebSocket: {msg}")
    elif msg.get('e') == 'error' or 'error' in msg:
         logging.error(f"WebSocket Stream Error Message: {msg.get('m', msg.get('error', 'Unknown error structure'))}")
    else:
        logging.warning(f"Unhandled WS Message: {msg}")


def start_specific_websocket_stream(new_symbol_to_stream):
    global current_stream_name_active, websocket_data_flow_active, twm
    
    # Étape 1: S'assurer que le manager TWM lui-même est démarré.
    if not ensure_twm_globally_started(): # Cette fonction gère ses propres logs et st.error
        logging.error("start_specific_websocket_stream: Cannot start stream because TWM global manager failed to start.")
        return None

    # Étape 2: Démarrer le stream kline spécifique.
    new_symbol_upper = new_symbol_to_stream.upper()
    logging.info(f"start_specific_websocket_stream: Attempting to start kline stream for {new_symbol_upper}.")
    
    returned_stream_name_from_lib = None 
    try:
        logging.info(f"PRE-CALL to twm.start_kline_socket for {new_symbol_upper}")
        returned_stream_name_from_lib = twm.start_kline_socket(
            symbol=new_symbol_upper,
            callback=handle_kline_message
        )
        logging.info(f"POST-CALL to twm.start_kline_socket. Returned stream_name: {returned_stream_name_from_lib}")

        if returned_stream_name_from_lib:
            current_stream_name_active = returned_stream_name_from_lib 
            websocket_data_flow_active.set() 
            logging.info(f"Successfully started kline stream for {new_symbol_upper} with name {current_stream_name_active}. websocket_data_flow_active is SET.")
        else:
            logging.error(f"Failed to start kline socket for {new_symbol_upper}. twm.start_kline_socket returned None or empty.")
            st.error(f"Impossible de démarrer le flux pour {new_symbol_upper}. Vérifiez la console (POST-CALL).")
            websocket_data_flow_active.clear()
        return returned_stream_name_from_lib
    except RuntimeError as e:
        if "There is no current event loop" in str(e):
            logging.error(f"start_specific_websocket_stream: RuntimeError: No current event loop during twm.start_kline_socket() for {new_symbol_upper}. Error: {e}", exc_info=True)
            st.error(f"Erreur asyncio pour {new_symbol_upper} lors du démarrage du stream: {e}.")
        else:
            logging.error(f"start_specific_websocket_stream: Generic RuntimeError during twm.start_kline_socket() for {new_symbol_upper}: {e}", exc_info=True)
            st.error(f"Erreur Runtime pour {new_symbol_upper} lors du démarrage du stream: {e}")
        websocket_data_flow_active.clear()
        return None
    except Exception as e:
        logging.error(f"CRITICAL EXCEPTION during twm.start_kline_socket for {new_symbol_upper}: {e}", exc_info=True)
        st.error(f"Erreur critique lors du démarrage du flux pour {new_symbol_upper}: {e}")
        websocket_data_flow_active.clear()
        return None

# --- Interface Streamlit ---
st.set_page_config(layout="wide", page_title="Tableau de Bord Crypto Live")
st.title("📈 Tableau de Bord Crypto Live (Binance - Bougies 1m)")

# Tentative de démarrage du TWM au premier chargement du script (si pas déjà fait par une interaction)
# Cela est important pour voir si l'erreur "no event loop" se produit dès le début.
if 'initial_twm_start_attempted_flag' not in st.session_state:
    logging.info("UI Scope: First run, attempting to ensure TWM is started.")
    ensure_twm_globally_started()
    st.session_state.initial_twm_start_attempted_flag = True

if 'klines_df' not in st.session_state:
    st.session_state.klines_df = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    st.session_state.klines_df.set_index('time', inplace=True)
if 'symbol_ui_expects_streaming' not in st.session_state: 
    st.session_state.symbol_ui_expects_streaming = ""
if 'last_ui_update_time' not in st.session_state:
    st.session_state.last_ui_update_time = time.time()
if 'symbol_input_field_value' not in st.session_state: 
    st.session_state.symbol_input_field_value = "BTCUSDT"


symbol_input_text = st.text_input("Entrez le symbole (ex: BTCUSDT, ETHUSDT):", 
                                  value=st.session_state.symbol_input_field_value).upper()

col_btn1, _ = st.columns([1,3]) 
start_button_is_pressed = col_btn1.button(f"Démarrer/Changer Stream pour {symbol_input_text}", key="start_stream_btn", use_container_width=True)

should_initiate_stream_change = False
if start_button_is_pressed and symbol_input_text:
    should_initiate_stream_change = True
    logging.info(f"Start button pressed for symbol: {symbol_input_text}")
elif symbol_input_text and symbol_input_text != st.session_state.symbol_ui_expects_streaming:
    should_initiate_stream_change = True
    logging.info(f"Symbol input changed to: {symbol_input_text}, different from current UI expectation: {st.session_state.symbol_ui_expects_streaming}")

if should_initiate_stream_change:
    st.session_state.symbol_input_field_value = symbol_input_text
    
    with st.spinner(f"Traitement de la requête pour {symbol_input_text}..."):
        logging.info(f"UI: Stream change/start process initiated for {symbol_input_text}")
        
        if current_stream_name_active: # S'il y a un stream actif à arrêter
            logging.info(f"UI: Stopping existing stream: {current_stream_name_active} (associated with UI symbol {st.session_state.symbol_ui_expects_streaming})")
            try:
                twm.stop_socket(current_stream_name_active) # Utilise l'objet twm global
                logging.info(f"UI: twm.stop_socket called for {current_stream_name_active}. Adding a 1s delay...")
            except Exception as e:
                logging.error(f"UI: Error during twm.stop_socket for {current_stream_name_active}: {e}", exc_info=True)
            
            time.sleep(1) 
            current_stream_name_active = None 
            websocket_data_flow_active.clear()
            st.session_state.symbol_ui_expects_streaming = "" 
        
        logging.info(f"UI: Attempting to start new stream for {symbol_input_text} via start_specific_websocket_stream function")
        returned_stream_name = start_specific_websocket_stream(symbol_input_text) 
        
        if returned_stream_name: 
            st.session_state.symbol_ui_expects_streaming = symbol_input_text 
            st.session_state.klines_df = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            st.session_state.klines_df.set_index('time', inplace=True)
            st.success(f"Connexion au flux pour {symbol_input_text} (bougies 1m) initiée. Attente des données...")
            logging.info(f"UI: Stream for {symbol_input_text} initiated successfully.")
            st.experimental_rerun()
        else:
            logging.warning(f"UI: Stream start failed for {symbol_input_text}.")
            st.error(f"Échec du démarrage du flux pour {symbol_input_text}. Vérifiez la console.")

elif not symbol_input_text and start_button_is_pressed:
    st.warning("Veuillez entrer un symbole.")

st.header(f"Données en direct pour {st.session_state.symbol_ui_expects_streaming if st.session_state.symbol_ui_expects_streaming else 'Aucun Symbole'}")
col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
metric_price = col_metric1.empty()
metric_high = col_metric2.empty()
metric_low = col_metric3.empty()
metric_volume = col_metric4.empty()

chart_price_placeholder = st.empty()
chart_volume_placeholder = st.empty()
latest_data_placeholder = st.empty()

if st.session_state.symbol_ui_expects_streaming and websocket_data_flow_active.is_set():
    logging.debug(f"UI Update Loop: Stream for {st.session_state.symbol_ui_expects_streaming} is active. Checking queue.")
    new_data_received_this_cycle = False
    try:
        while not data_queue.empty():
            kline = data_queue.get_nowait()
            new_kline_df = pd.DataFrame([kline])
            new_kline_df.set_index('time', inplace=True)
            st.session_state.klines_df = pd.concat([st.session_state.klines_df, new_kline_df])
            st.session_state.klines_df = st.session_state.klines_df[~st.session_state.klines_df.index.duplicated(keep='last')]
            st.session_state.klines_df.sort_index(inplace=True)
            if len(st.session_state.klines_df) > MAX_KLINES_IN_CHART:
                st.session_state.klines_df = st.session_state.klines_df.iloc[-MAX_KLINES_IN_CHART:]
            new_data_received_this_cycle = True

        if not st.session_state.klines_df.empty:
            if new_data_received_this_cycle:
                last_kline = st.session_state.klines_df.iloc[-1]
                prev_price = st.session_state.klines_df['close'].iloc[-2] if len(st.session_state.klines_df) > 1 else last_kline['close']
                price_delta_val = ((last_kline['close'] - prev_price) / prev_price * 100) if prev_price != 0 else 0.0
                metric_price.metric(label="Dernier Prix", value=f"{last_kline['close']:.4f}", delta=f"{price_delta_val:.2f}%")
                metric_high.metric(label="Plus Haut (bougie)", value=f"{last_kline['high']:.4f}")
                metric_low.metric(label="Plus Bas (bougie)", value=f"{last_kline['low']:.4f}")
                metric_volume.metric(label="Volume (bougie)", value=f"{last_kline['volume']:.2f}")
            
            chart_price_placeholder.line_chart(st.session_state.klines_df['close'], use_container_width=True)
            chart_volume_placeholder.bar_chart(st.session_state.klines_df['volume'], use_container_width=True)
            latest_data_placeholder.dataframe(st.session_state.klines_df.tail(5).sort_index(ascending=False), use_container_width=True)
            st.session_state.last_ui_update_time = time.time()
    except queue.Empty:
        pass
    except Exception as e:
        logging.error(f"Erreur dans la boucle UI principale : {e}", exc_info=True)
        st.error(f"Erreur d'affichage: {e}")

    if time.time() - st.session_state.last_ui_update_time > DATA_FETCH_INTERVAL_SECONDS:
        st.experimental_rerun()
        
elif st.session_state.symbol_ui_expects_streaming and not websocket_data_flow_active.is_set():
    st.warning(f"Le flux pour {st.session_state.symbol_ui_expects_streaming} n'est pas actif. Veuillez vérifier la console et réessayer.")
else:
    st.info("Entrez un symbole et cliquez sur 'Démarrer/Changer Stream' pour commencer.")