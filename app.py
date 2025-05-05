from flask import Flask, redirect, request, session, url_for, render_template
from google_auth_oauthlib.flow import Flow
import os
import pathlib
import json


from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = "replace-this-with-a-secret"

# Path to your OAuth credentials
CLIENT_SECRETS_FILE = "client_secrets.json"

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
REDIRECT_URI = "https://clearengine-auth.onrender.com/oauth2callback"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    client_secrets = json.loads(os.environ["GOOGLE_CLIENT_SECRETS"])
    flow = Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    client_secrets = json.loads(os.environ["GOOGLE_CLIENT_SECRETS"])
    flow = Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Rebuild the state from the session
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # ⚠️ You can store these in a secure DB or send to your analysis script
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    # For now, just print to terminal and show confirmation
    print("🔐 Credentials received:", token_data)

    return "✅ Authorization complete. You can now close this window."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

