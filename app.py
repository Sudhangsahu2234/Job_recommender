from flask import Flask, render_template, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename
from Ats import UniversalATSChecker
from Job_recommender import extract_skills, extract_experience, search_jobs
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['JSEARCH_API_KEY'] = 'ak_jiti1d0u7bjjhqpr138j6jp7yc23js47zstuc2i8756hosr'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize ATS checker
ats_checker = UniversalATSChecker()

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Extract text from uploaded file
        resume_text = ats_checker.extract_text_from_file(filepath)

        if "Error reading file" in resume_text:
            flash('Error reading the file. Please try a different format.')
            os.remove(filepath)
            return redirect(url_for('home'))

        # Perform ATS analysis
        ats_results = ats_checker.calculate_overall_ats_score(resume_text, filename)
        ats_report = ats_checker.generate_detailed_report(ats_results)

        # Extract skills and experience for job recommendations
        skills = extract_skills(resume_text)
        experience = extract_experience(resume_text)

        # Search for jobs
        if skills:
            if app.config['JSEARCH_API_KEY'] != 'YOUR_RAPIDAPI_KEY':
                jobs_data = search_jobs(skills, experience, app.config['JSEARCH_API_KEY'])
                if jobs_data:
                    jobs = jobs_data[:10]
                else:
                    jobs = []
            else:
                jobs = None
        else:
            jobs = None

        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

        return render_template('results.html',
                             ats_results=ats_results,
                             ats_report=ats_report,
                             skills=skills,
                             experience=experience,
                             jobs=jobs)

    else:
        flash('Invalid file type. Please upload PDF, DOCX, DOC, or TXT files.')
        return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)