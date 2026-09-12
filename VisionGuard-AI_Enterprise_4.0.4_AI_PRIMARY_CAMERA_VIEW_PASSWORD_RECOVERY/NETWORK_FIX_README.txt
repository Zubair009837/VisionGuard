V4 NETWORK FIX

If the UI previously showed Network Error, V4 uses a Vite dev proxy:
Browser -> /api -> Vite -> http://127.0.0.1:8000 -> FastAPI
This avoids browser CORS completely during local development.

If you still see Network Error, open browser DevTools (F12) -> Network, click Smart Search, and the failed request should show /api/historical-recordings/search.
