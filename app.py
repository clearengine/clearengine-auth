from flask import Flask, redirect, request, session, url_for, render_template
from google_auth_oauthlib.flow import Flow
from datetime import datetime
import os
import pathlib
import json
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = "replace-this-with-a-secret"

# OAuth client secrets (stored in env variable as JSON string)
CLIENT_SECRETS_FILE = "client_secrets.json"

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/drive.file"  # For Drive upload
]
REDIRECT_URI = "https://clearengine-auth.onrender.com/oauth2callback"  # Your deployed callback URI


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/set_client", methods=["POST"])
def set_client():
    session["client_name"] = request.form["client_name"]
    return redirect("/login")

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
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(authorization_url)


# 🔐 One-time route just for you to authorize Google Drive
@app.route("/authorize_drive")
def authorize_drive():
    client_secrets = json.loads(os.environ["GOOGLE_CLIENT_SECRETS"])
    flow = Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI + "?drive_setup=true"
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    client_secrets = json.loads(os.environ["GOOGLE_CLIENT_SECRETS"])
    redirect_uri = REDIRECT_URI
    if "drive_setup" in request.url:
        redirect_uri += "?drive_setup=true"

    flow = Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    if "drive_setup" in request.url:
        # Save your Drive credentials to a local file
        with open("drive_credentials.json", "w") as f:
            json.dump({
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes
            }, f)
        return "✅ Drive access authorized and saved to drive_credentials.json"

    # Normal user session handling (GA flow)
    session["token"] = credentials.token
    session["refresh_token"] = credentials.refresh_token
    session["token_uri"] = credentials.token_uri
    session["client_id"] = credentials.client_id
    session["client_secret"] = credentials.client_secret

    return redirect("/report")

