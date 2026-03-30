import os
from flask import Flask, request, render_template, flash, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import subprocess
import sys


# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'ir'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'supersecretkey'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('yaml', filename, as_attachment=True)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        print("--- POST request received ---")

        if 'file' not in request.files:
            print("ERROR: 'file' key not found in request.files. Check your HTML <input name='file'>")
            flash('No file part')
            return redirect(request.url)


        file = request.files['file']
        print(f"DEBUG: Found file: {file.filename}")

        if file.filename == '':
            print("ERROR: Filename is empty (user didn't select a file)")
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            destination = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"DEBUG: Attempting to save to: {os.path.abspath(destination)}")
            file.save(destination)
            env = os.environ.copy()
            env['DAFILE'] = filename.rsplit('.', 1)[0].lower()
            subprocess.run(['python', 'translator.py'], env=env)
            flash('File successfully uploaded')

            return redirect(url_for('download_file', filename=f"{filename.rsplit('.', 1)[0].lower()}.yaml"))
        else:
            print(
                f"ERROR: File extension not allowed. Extension was: {file.filename.rsplit('.', 1)[1] if '.' in file.filename else 'None'}")
            flash('Invalid file extension')

    return render_template('index.html')



if __name__ == '__main__':
    # Ensure the upload folder exists
    # Run the app
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'yaml'), exist_ok=True)
    app.run(debug=True)

