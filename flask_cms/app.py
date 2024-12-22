from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import zipfile
import shutil

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Models
class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Theme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=False)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(100), nullable=False)

# Route to serve dynamic pages
@app.route('/<path:subpath>', methods=['GET', 'POST'])
@app.route('/', defaults={'subpath': ''}, methods=['GET', 'POST'])
def serve_page(subpath):
    try:
        path = f'/{subpath}' if subpath else '/'
        page = Page.query.filter_by(path=path).first()

        if not page:
            abort(404, description="Page not found.")

        theme = Theme.query.filter_by(active=True).first()
        if not theme:
            abort(500, description="No active theme found.")

        # Fetch all pages for the menu
        all_pages = Page.query.all()

        # Fetch CMS name
        cms_name = Setting.query.filter_by(name="cms_name").first().value

        return render_template(
            f"themes/{theme.name}/base.html",
            title=page.title,
            content=page.content,
            pages=all_pages,
            cms_name=cms_name  # Pass CMS name to the template
        )
    except Exception as e:
        print(f"Error serving page: {e}")
        abort(500, description="Internal Server Error")

# Dashboard to manage pages, themes, and CMS name
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'add_page':
            path = request.form.get('path')
            title = request.form.get('title')
            content = request.form.get('content')

            if not path or not title or not content:
                flash('All fields are required!', 'error')
                return redirect(url_for('dashboard'))

            existing_page = Page.query.filter_by(path=path).first()
            if existing_page:
                flash('A page with this path already exists!', 'error')
                return redirect(url_for('dashboard'))

            new_page = Page(path=path, title=title, content=content)
            db.session.add(new_page)
            db.session.commit()
            flash('Page added successfully!', 'success')

        elif form_type == 'update_cms_name':
            cms_name = request.form.get('cms_name')
            setting = Setting.query.filter_by(name="cms_name").first()
            setting.value = cms_name
            db.session.commit()
            flash('CMS name updated successfully!', 'success')

        return redirect(url_for('dashboard'))

    pages = Page.query.all()
    themes = Theme.query.all()
    cms_name = Setting.query.filter_by(name="cms_name").first().value
    return render_template('dashboard.html', pages=pages, themes=themes, cms_name=cms_name)

# Upload and extract themes
@app.route('/upload-theme', methods=['POST'])
def upload_theme():
    if 'theme_zip' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['theme_zip']
    if file.filename == '':
        flash('No selected file.', 'error')
        return redirect(url_for('dashboard'))

    filename = secure_filename(file.filename)
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(zip_path)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            extracted_folder = os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0])
            zip_ref.extractall(extracted_folder)
            print(f"Extracted files: {zip_ref.namelist()}")
    except zipfile.BadZipFile:
        flash('Invalid ZIP file.', 'error')
        os.remove(zip_path)
        return redirect(url_for('dashboard'))

    theme_name = filename.split('.')[0]
    templates_folder = os.path.join('templates/themes', theme_name)
    static_folder = os.path.join('static/themes', theme_name)

    os.makedirs(templates_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    try:
        for root, _, files in os.walk(extracted_folder):
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith('.html'):
                    shutil.move(file_path, os.path.join(templates_folder, file))
                elif file.endswith('.css'):
                    shutil.move(file_path, os.path.join(static_folder, file))
        shutil.rmtree(extracted_folder)
    except Exception as e:
        flash(f'Error processing theme files: {e}', 'error')
        os.remove(zip_path)
        return redirect(url_for('dashboard'))

    os.remove(zip_path)

    if not Theme.query.filter_by(name=theme_name).first():
        new_theme = Theme(name=theme_name)
        db.session.add(new_theme)
        db.session.commit()

    flash(f'Theme "{theme_name}" uploaded successfully!', 'success')
    return redirect(url_for('dashboard'))

# Activate a theme
@app.route('/activate-theme/<theme_name>', methods=['POST'])
def activate_theme(theme_name):
    theme = Theme.query.filter_by(name=theme_name).first_or_404()
    Theme.query.update({Theme.active: False})
    theme.active = True
    db.session.commit()
    flash(f'Theme "{theme_name}" activated!', 'success')
    return redirect(url_for('dashboard'))

# Delete a theme
@app.route('/delete-theme/<theme_name>', methods=['POST'])
def delete_theme(theme_name):
    theme = Theme.query.filter_by(name=theme_name).first_or_404()

    if theme.active:
        flash('Cannot delete an active theme. Please activate another theme first.', 'error')
        return redirect(url_for('dashboard'))

    templates_folder = os.path.join('templates/themes', theme.name)
    static_folder = os.path.join('static/themes', theme.name)

    if os.path.exists(templates_folder):
        shutil.rmtree(templates_folder)
    if os.path.exists(static_folder):
        shutil.rmtree(static_folder)

    db.session.delete(theme)
    db.session.commit()
    flash(f'Theme "{theme_name}" deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

# Delete a page
@app.route('/delete-page/<int:page_id>', methods=['POST'])
def delete_page(page_id):
    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    flash('Page deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

# Initialize the database and seed the CMS name
@app.route('/init-db')
def init_db():
    db.create_all()

    # Seed CMS name if not set
    if not Setting.query.filter_by(name="cms_name").first():
        cms_name = Setting(name="cms_name", value="My CMS")
        db.session.add(cms_name)

    flash('Database initialized!', 'success')
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
