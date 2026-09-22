import sys
import os
import traceback

# Add root directory to sys.path so app.py and utils can be imported in Vercel Serverless
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from app import app

    class VercelPathFix:
        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app

        def __call__(self, environ, start_response):
            path = environ.get('PATH_INFO', '')
            # Handle all possible Vercel serverless prefix rewrites
            for prefix in ['/api/index.py', '/api/index', '/api']:
                if path == prefix or path == prefix + '/':
                    environ['PATH_INFO'] = '/'
                    break
                elif path.startswith(prefix + '/'):
                    environ['PATH_INFO'] = path[len(prefix):]
                    break

            if not environ.get('PATH_INFO'):
                environ['PATH_INFO'] = '/'

            return self.wsgi_app(environ, start_response)

    app.wsgi_app = VercelPathFix(app.wsgi_app)

except Exception as e:
    error_trace = traceback.format_exc()
    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        return [f"App failed to start. Error:\n\n{error_trace}".encode('utf-8')]
