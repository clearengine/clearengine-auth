from flask import Flask, redirect, request, session, url_for, render_template
from google_auth_oauthlib.flow import Flow
from datetime import datetime
import os
import json
from werkzeug.middleware.proxy_fix import ProxyFix
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = "replace-this-with-a-secret"

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

    session["token"] = credentials.token
    session["refresh_token"] = credentials.refresh_token
    session["token_uri"] = credentials.token_uri
    session["client_id"] = credentials.client_id
    session["client_secret"] = credentials.client_secret

    return redirect("/report")

def upload_to_drive(filepath, filename):
    with open("drive_credentials.json", "r") as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )

    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": filename,
        "parents": ["1SY6n4AM8fz9KwoPOijfw1rbS7hLNInCI"]  # Upload to specific folder
    }
    media = MediaFileUpload(filepath, resumable=True)

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    return uploaded_file.get("id")

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

    property_id = "351926152"
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

    report_path = f"{folder_path}/ga4-report-{date_str}.json"
    with open(report_path, "w") as f:
        json.dump({"report": output}, f, indent=2)

    uploaded_id = upload_to_drive(report_path, f"ga4-report-{date_str}.json")

    return {"report_uploaded_to_drive_id": uploaded_id, "report": output}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
