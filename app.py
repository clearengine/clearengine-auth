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

# OAuth client secrets (loaded from environment variable)
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/drive.file"
]
REDIRECT_URI = "https://clearengine-auth.onrender.com/oauth2callback"


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


# ✅ One-time route for Drive setup
@app.route("/authorize_drive")
def authorize_drive():
    session["drive_setup"] = True  # Use session instead of URI param
    return redirect("/login")


@app.route("/oauth2callback")
def oauth2callback():
    client_secrets = json.loads(os.environ["GOOGLE_CLIENT_SECRETS"])
    flow = Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    if session.get("drive_setup"):
        session.pop("drive_setup", None)
        return f"<pre>{json.dumps({
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }, indent=2)}</pre>"


    # Normal GA flow
    session["token"] = credentials.token
    session["refresh_token"] = credentials.refresh_token
    session["token_uri"] = credentials.token_uri
    session["client_id"] = credentials.client_id
    session["client_secret"] = credentials.client_secret

    return redirect("/report")


from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2.credentials import Credentials


@app.route("/report")
def run_report():
    creds = Credentials(
        token=session.get("token"),
        refresh_token=session.get("refresh_token"),
        token_uri=session.get("token_uri"),
        client_id=session.get("client_id"),
        client_secret=session.get("client_secret"),
        scopes=SCOPES
    )

    property_id = "351926152"  # Replace with dynamic ID later
    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date="2023-01-01", end_date="today")],
        dimensions=[
            Dimension(name="month"),
            Dimension(name="sourceMedium"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="totalRevenue"),
            Metric(name="purchaseRevenue"),
            Metric(name="grossPurchaseRevenue"),
        ]
    )

    response = client.run_report(request)
    output = []

    for row in response.rows:
        dimension_headers = list(response.dimension_headers)
        metric_headers = list(response.metric_headers)
        dimension_values = list(row.dimension_values)
        metric_values = list(row.metric_values)

        output.append({
            header.name: value.value
            for header, value in zip(dimension_headers + metric_headers, dimension_values + metric_values)
        })

    client_name = session.get("client_name", "unknown_client")
    date_str = datetime.today().strftime("%Y-%m-%d")
    folder_path = f"data/{client_name}"
    os.makedirs(folder_path, exist_ok=True)

    with open(f"{folder_path}/ga4-report-{date_str}.json", "w") as f:
        json.dump({"report": output}, f, indent=2)

    return {"report": output}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
