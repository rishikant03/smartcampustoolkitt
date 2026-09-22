import sys
import os
import traceback

# Add root directory to sys.path so app.py and utils can be imported in Vercel Serverless
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from app import app
except Exception as e:
    error_trace = traceback.format_exc()
    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [f"App failed to start. Error:\n\n{error_trace}".encode('utf-8')]
