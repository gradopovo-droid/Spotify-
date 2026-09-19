import os
import secrets
import urllib.parse
import urllib.request
import json

from http.server import BaseHTTPRequestHandler


CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "https://adimax-five.vercel.app/api/callback"

SCOPE = "user-read-private user-read-email"


class handler(BaseHTTPRequestHandler):

    def send_html(self, html, status=200, extra_headers=None):
        data = html.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))

        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)

        self.end_headers()
        self.wfile.write(data)

    def redirect(self, url, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", url)

        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)

        self.end_headers()

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # HOME
        if path in ["/", "/api", "/api/"]:

            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport"
                      content="width=device-width, initial-scale=1">
                <title>AdiMax Spotify</title>

                <style>
                    body {
                        background: #111;
                        color: white;
                        font-family: Arial;
                        text-align: center;
                        padding-top: 100px;
                    }

                    a {
                        display: inline-block;
                        padding: 15px 25px;
                        background: #1DB954;
                        color: white;
                        text-decoration: none;
                        border-radius: 25px;
                        font-weight: bold;
                    }
                </style>
            </head>

            <body>
                <h1>🎵 AdiMax Spotify</h1>
                <p>Connect your Spotify account</p>

                <a href="/api/login">
                    Login with Spotify
                </a>
            </body>
            </html>
            """

            self.send_html(html)
            return

        # LOGIN
        if path == "/api/login":

            if not CLIENT_ID or not CLIENT_SECRET:
                self.send_html(
                    "<h2>Spotify credentials missing.</h2>"
                    "<p>Add SPOTIFY_CLIENT_ID and "
                    "SPOTIFY_CLIENT_SECRET in Vercel.</p>",
                    500
                )
                return

            state = secrets.token_urlsafe(32)

            params = {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
                "state": state
            }

            spotify_url = (
                "https://accounts.spotify.com/authorize?"
                + urllib.parse.urlencode(params)
            )

            headers = [
                (
                    "Set-Cookie",
                    f"spotify_state={state}; HttpOnly; Secure; "
                    "SameSite=Lax; Path=/"
                )
            ]

            self.redirect(spotify_url, headers)
            return

        # CALLBACK
        if path == "/api/callback":

            error = query.get("error", [None])[0]

            if error:
                self.send_html(
                    f"<h2>Spotify Error</h2><p>{error}</p>",
                    400
                )
                return

            code = query.get("code", [None])[0]
            state = query.get("state", [None])[0]

            if not code or not state:
                self.send_html(
                    "<h2>Missing code or state.</h2>",
                    400
                )
                return

            # Read saved state from cookie
            cookie = self.headers.get("Cookie", "")
            saved_state = None

            for item in cookie.split(";"):
                item = item.strip()

                if item.startswith("spotify_state="):
                    saved_state = item.split("=", 1)[1]

            if not saved_state or not secrets.compare_digest(
                saved_state,
                state
            ):
                self.send_html(
                    "<h2>Invalid state.</h2>"
                    "<p>Please try Spotify login again.</p>",
                    400
                )
                return

            # Exchange authorization code for token
            token_data = urllib.parse.urlencode({
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI
            }).encode()

            request = urllib.request.Request(
                "https://accounts.spotify.com/api/token",
                data=token_data,
                method="POST"
            )

            auth = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
            auth_header = (
                "Basic "
                + __import__("base64")
                .b64encode(auth)
                .decode()
            )

            request.add_header(
                "Authorization",
                auth_header
            )

            request.add_header(
                "Content-Type",
                "application/x-www-form-urlencoded"
            )

            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    token_response = json.loads(
                        response.read().decode()
                    )

            except Exception as e:
                self.send_html(
                    "<h2>Token Error</h2>"
                    f"<p>{str(e)}</p>",
                    500
                )
                return

            access_token = token_response.get("access_token")

            if not access_token:
                self.send_html(
                    "<h2>Access token not received.</h2>"
                    f"<pre>{json.dumps(token_response, indent=2)}</pre>",
                    500
                )
                return

            # Get Spotify user profile
            profile_request = urllib.request.Request(
                "https://api.spotify.com/v1/me"
            )

            profile_request.add_header(
                "Authorization",
                f"Bearer {access_token}"
            )

            try:
                with urllib.request.urlopen(
                    profile_request,
                    timeout=15
                ) as response:

                    profile = json.loads(
                        response.read().decode()
                    )

            except Exception as e:
                self.send_html(
                    "<h2>Profile Error</h2>"
                    f"<p>{str(e)}</p>",
                    500
                )
                return

            name = profile.get("display_name") or "Spotify User"
            email = profile.get("email") or "Not available"

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport"
                      content="width=device-width, initial-scale=1">

                <title>Spotify Connected</title>

                <style>
                    body {{
                        background: #111;
                        color: white;
                        font-family: Arial;
                        text-align: center;
                        padding: 70px 20px;
                    }}

                    .box {{
                        max-width: 450px;
                        margin: auto;
                        padding: 30px;
                        border-radius: 20px;
                        background: #181818;
                    }}

                    .green {{
                        color: #1DB954;
                    }}
                </style>
            </head>

            <body>
                <div class="box">
                    <h1 class="green">✓ Connected</h1>
                    <h2>{name}</h2>
                    <p>{email}</p>
                    <p>Spotify account connected successfully.</p>
                </div>
            </body>
            </html>
            """

            self.send_html(html)
            return

        # 404
        self.send_html(
            "<h1>404</h1><p>Page not found.</p>",
            404
        )
