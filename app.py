from flask import Flask, redirect, request, session, url_for, render_template
from google_auth_oauthlib.flow import Flow
import os
import pathlib
import json

app = Flask(__name__)
app.secret_key = "replace-this-with-a-secret"

# Path to your OAuth credentials
CLIENT_SECRETS_FILE = "client_secrets.json"

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
REDIRECT_URI = "http://localhost:5000/oauth2callback"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
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
    state = session["state"]
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    with open("token.json", "w") as token_file:
        json.dump(token_data, token_file)

    return "✅ Authorization successful. You can now pull GA4 data."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

