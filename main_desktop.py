import socket
import threading
import sys
import webview
from app import app  # Import ReClip's Flask app instance

def find_free_port():
    """Finds an open localhost port dynamically to avoid address conflicts."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

def run_flask_server(port):
    """Runs Flask quietly in the background without debug overhead."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    port = find_free_port()

    # Start Flask backend in a separate daemon thread
    server_thread = threading.Thread(target=run_flask_server, args=(port,))
    server_thread.daemon = True
    server_thread.start()

    # Create PyWebView GUI window
    window = webview.create_window(
        title="ReClip - Desktop",
        url=f"http://127.0.0.1:{port}",
        width=1000,
        height=750,
        resizable=True,
        min_size=(800, 600)
    )

    # Start the desktop window (uses GTK cleanly on Linux systems via venv system-site-packages)
    webview.start(gui='gtk')
    
    sys.exit(0)