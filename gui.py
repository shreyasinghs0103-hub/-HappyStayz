import threading
import webview
from app import app

def start_flask():
    app.run(host='127.0.0.1', port=5000, threaded=True, debug=False)

if __name__ == '__main__':
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()

    webview.create_window(
        title='HappyStayz Admin Dashboard', 
        url='http://127.0.0.1:5000/admin/staff',
        width=1200,
        height=800,
        resizable=True
    )
    webview.start()