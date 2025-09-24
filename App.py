import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.utils import secure_filename
import pandas as pd
from math import ceil
from flask import request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # change this

# Config for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, role='user'):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

users = {
    'admin': User('1', 'admin', 'password123', role='admin'),
    'user': User('2', 'user', 'pass456', role='user')
}

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == user_id:
            return user
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_current_csv_path():
    if 'uploaded_csv' in session:
        return os.path.join(app.config['UPLOAD_FOLDER'], session['uploaded_csv'])
    return os.path.join('Data', 'dowry_cases_sample.csv')

# Mapping regions to lat/lon coordinates for map plotting
REGION_COORDINATES = {
    'delhi': (28.6139, 77.2090),
    'mumbai': (19.0760, 72.8777),
    'hyderabad': (17.3850, 78.4867),
    'bangalore': (12.9716, 77.5946),
    'kolkata': (22.5726, 88.3639),
    'chennai': (13.0827, 80.2707),
    'pune': (18.5204, 73.8567),
    # Add more if necessary
}

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_csv():
    message = None
    if request.method == 'POST':
        if 'file' not in request.files:
            message = 'No file part'
            return render_template('upload_csv.html', message=message)
        file = request.files['file']
        if file.filename == '':
            message = 'No selected file'
            return render_template('upload_csv.html', message=message)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            session['uploaded_csv'] = filename
            message = f'File "{filename}" uploaded successfully and active!'
        else:
            message = 'Invalid file type, only CSV allowed'
    return render_template('upload_csv.html', message=message)

@app.route('/reset-data')
@login_required
def reset_data():
    session.pop('uploaded_csv', None)
    flash("Data reset to default sample dataset.")
    return redirect(url_for('upload_csv'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)
        if user and user.password == password:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    csv_path = get_current_csv_path()
    df = pd.read_csv(csv_path)
    total_cases = int(len(df))
    open_cases = int(len(df[df['status'].str.lower() == 'open']))
    closed_cases = int(len(df[df['status'].str.lower() == 'closed']))
    regions_covered = int(df['region'].nunique())
    yearly_totals = df.groupby('year').size().sort_index()
    yearly_open = df[df['status'].str.lower() == 'open'].groupby('year').size().reindex(yearly_totals.index, fill_value=0).sort_index()
    yearly_closed = df[df['status'].str.lower() == 'closed'].groupby('year').size().reindex(yearly_totals.index, fill_value=0).sort_index()
    trend_labels = [str(y) for y in yearly_totals.index.tolist()]
    total_trend = [int(x) for x in yearly_totals.values.tolist()]
    open_trend = [int(x) for x in yearly_open.values.tolist()]
    closed_trend = [int(x) for x in yearly_closed.values.tolist()]
    active_file = session.get('uploaded_csv', 'Sample Dataset')
    return render_template(
        'index.html',
        total_cases=total_cases,
        open_cases=open_cases,
        closed_cases=closed_cases,
        num_regions=regions_covered,  # changed variable name to match new card title
        active_file=active_file,
        trend_labels=trend_labels,
        total_trend=total_trend,
        open_trend=open_trend,
        closed_trend=closed_trend
    )

@app.route('/trends')
@login_required
def trends():
    csv_path = get_current_csv_path()
    df = pd.read_csv(csv_path)
    case_counts = df.groupby('year').size()
    fig1, ax1 = plt.subplots()
    ax1.bar(case_counts.index.astype(str), case_counts.values)
    ax1.set_title('Dowry Cases Over Years')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Number of Cases')
    img1 = io.BytesIO()
    plt.savefig(img1, format='png')
    plt.close(fig1)
    img1.seek(0)
    bar_chart_url = base64.b64encode(img1.getvalue()).decode()
    case_type_counts = df['case_type'].value_counts()
    fig2, ax2 = plt.subplots()
    ax2.pie(case_type_counts.values, labels=case_type_counts.index, autopct='%1.1f%%', startangle=140)
    ax2.set_title('Dowry Case Types Distribution')
    img2 = io.BytesIO()
    plt.savefig(img2, format='png')
    plt.close(fig2)
    img2.seek(0)
    pie_chart_url = base64.b64encode(img2.getvalue()).decode()
    return render_template('trends.html', bar_chart_url=bar_chart_url, pie_chart_url=pie_chart_url)

@app.route('/hotspots')
@login_required
def hotspots():
    csv_path = get_current_csv_path()
    df = pd.read_csv(csv_path)
    region_counts = df['region'].value_counts()
    fig, ax = plt.subplots()
    ax.bar(region_counts.index, region_counts.values)
    ax.set_title('Dowry Cases by Region')
    ax.set_xlabel('Region')
    ax.set_ylabel('Number of Cases')
    plt.xticks(rotation=45, ha='right')
    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png')
    plt.close(fig)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    return render_template('hotspots.html', plot_url=plot_url)

@app.route('/hotspots-map')
@login_required
def hotspots_map():
    hotspots = [
        {'region': 'Delhi', 'lat': 28.6139, 'lon': 77.2090, 'cases': 12},       # Red
        {'region': 'Maharashtra', 'lat': 19.0760, 'lon': 72.8777, 'cases': 9},  # Coral
        {'region': 'Karnataka', 'lat': 12.9716, 'lon': 77.5946, 'cases': 6},    # Gold
        {'region': 'Tamil Nadu', 'lat': 13.0827, 'lon': 80.2707, 'cases': 3},   # Green
        {'region': 'West Bengal', 'lat': 22.5726, 'lon': 88.3639, 'cases': 8},  # Coral
        {'region': 'Uttar Pradesh', 'lat': 26.8467, 'lon': 80.9462, 'cases': 5},# Gold
        {'region': 'Gujarat', 'lat': 23.0225, 'lon': 72.5714, 'cases': 7},      # Gold
        {'region': 'Rajasthan', 'lat': 26.9124, 'lon': 75.7873, 'cases': 4},    # Green
        {'region': 'Punjab', 'lat': 31.1471, 'lon': 75.3412, 'cases': 6},       # Gold
        {'region': 'Telangana', 'lat': 17.3850, 'lon': 78.4867, 'cases': 4},    # Green
        {'region': 'Haryana', 'lat': 29.0588, 'lon': 76.0856, 'cases': 3},      # Green
        {'region': 'Kerala', 'lat': 10.8505, 'lon': 76.2711, 'cases': 2},       # Green
        {'region': 'Odisha', 'lat': 20.9517, 'lon': 85.0985, 'cases': 4},       # Green
        {'region': 'Madhya Pradesh', 'lat': 22.9734, 'lon': 78.6569, 'cases': 5}# Gold
    ]
    return render_template('hotspots.html', hotspots_json=hotspots)


@app.route('/cases')
@login_required
def cases():
    df = pd.read_csv(get_current_csv_path())

    # Extract filters from query string
    region = request.args.get('region', '')
    year = request.args.get('year', '')
    case_type = request.args.get('case_type', '')
    status = request.args.get('status', '')

    # Apply filters
    if region:
        df = df[df['region'].str.contains(region, case=False, na=False)]
    if year:
        df = df[df['year'].astype(str) == year]
    if case_type:
        df = df[df['case_type'].str.contains(case_type, case=False, na=False)]
    if status:
        df = df[df['status'].str.contains(status, case=False, na=False)]

    # Pagination parameters from query string
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(df)
    total_pages = ceil(total / per_page)
    start = (page - 1) * per_page
    end = start + per_page

    df_page = df.iloc[start:end]

    # Prepare table HTML for the current page
    table_html = df_page.to_html(classes='table table-bordered table-hover table-striped align-middle', escape=False, index=False)

    # Pass unique dropdown options (all data, ignoring filters here)
    all_regions = sorted(pd.read_csv(get_current_csv_path())['region'].dropna().unique())
    all_years = sorted(pd.read_csv(get_current_csv_path())['year'].dropna().astype(str).unique())
    all_case_types = sorted(pd.read_csv(get_current_csv_path())['case_type'].dropna().unique())
    all_statuses = sorted(pd.read_csv(get_current_csv_path())['status'].dropna().unique())

    return render_template(
        'cases.html',
        table=table_html,
        regions=all_regions,
        years=all_years,
        case_types=all_case_types,
        statuses=all_statuses,
        selected_region=region,
        selected_year=year,
        selected_case_type=case_type,
        selected_status=status,
        page=page,
        total_pages=total_pages
    )
@app.route('/cases/download')
@login_required
def download_cases():
    csv_path = get_current_csv_path()
    df = pd.read_csv(csv_path)
    region = request.args.get('region', '').lower()
    year = request.args.get('year', '')
    case_type = request.args.get('case_type', '').lower()
    status = request.args.get('status', '').lower()
    if region:
        df = df[df['region'].str.lower().str.contains(region)]
    if year:
        df = df[df['year'].astype(str) == year]
    if case_type:
        df = df[df['case_type'].str.lower().str.contains(case_type)]
    if status:
        df = df[df['status'].str.lower().str.contains(status)]
    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={"Content-disposition": "attachment; filename=dowry_cases_filtered.csv"}
    )


if __name__ == '__main__':
    app.run(debug=True)
