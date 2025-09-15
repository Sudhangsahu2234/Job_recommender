import pandas as pd
import numpy as np
import PyPDF2
import requests
import spacy
import os
import re


nlp = spacy.load('en_core_web_sm')


API_HOST = 'https://api.openwebninja.com/jsearch'

SKILLS_DB = [
    'python', 'java', 'c++', 'c#', 'javascript', 'html', 'css', 'sql', 'mysql',
    'postgresql', 'mongodb'
]

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def extract_skills(text):
    """Extracts skills from the resume text using spaCy and a predefined list."""
    doc = nlp(text.lower())
    found_skills = set()


    for skill in SKILLS_DB:
        if skill in text.lower():
            found_skills.add(skill)


    for ent in doc.ents:
        if ent.label_ in ['ORG', 'PRODUCT']:
            if ent.text.lower() in SKILLS_DB:
                found_skills.add(ent.text.lower())

    return list(found_skills)

def extract_experience(text):
   
    experience_years = 0
    
    
    patterns = [
        r'(\d+)\s*to\s*(\d+)\s*years', 
        r'(\d+)\s*-\s*(\d+)\s*years', 
        r'(\d+)\+?\s*years' 
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                
                years = [int(y) for y in match]
                experience_years = max(experience_years, max(years))
            else:
                experience_years = max(experience_years, int(match))
                
    return experience_years

def search_jobs(skills, experience_years, api_key=None):
    """Searches for jobs on JSearch API based on skills and experience."""
    if not skills:
        return None

    if not api_key:
        print("API key not provided for job search.")
        return None

    # Select one skill from java, python, sql if available
    target_skills = ['java', 'python', 'sql']
    available_target_skills = [skill for skill in skills if skill.lower() in target_skills]

    if available_target_skills:
        selected_skill = available_target_skills[0]  # Select the first available
        query = f"{selected_skill} jobs"
    else:
        query = " ".join(skills) + " jobs"

    print(f"\nSearching for jobs with query: '{query}'\n")

    url = "https://api.openwebninja.com/jsearch/search"
    headers = {
        "x-api-key": api_key
    }
    params = {
        "query": query,
        "num_pages": "3"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        print("Full API response:", data)
        return data.get('data')
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching jobs: {e}")
        try:
            print(f"API Response: {e.response.json()}")
        except ValueError:
            print(f"API Response (raw): {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
        return None

def main():
   
    pdf_path = input("Enter the path to your resume PDF: ")

    if not os.path.exists(pdf_path):
        print("File not found. Please check the path.")
        return

    
    resume_text = extract_text_from_pdf(pdf_path)
    print("Extracted Resume Text (first 500 chars):", resume_text[:500])

   
    skills = extract_skills(resume_text)
    print("Extracted Skills:", skills)

    
    experience = extract_experience(resume_text)
    print(f"Extracted Experience: {experience} years")

    
    if skills:
        jobs = search_jobs(skills, experience)
        if jobs:
            print("\n--- Recommended Jobs ---")
            for job in jobs:
                print(f"Title: {job.get('job_title')}")
                print(f"Company: {job.get('employer_name')}")
                print(f"Location: {job.get('job_city')}, {job.get('job_country')}")
                print(f"Link: {job.get('job_apply_link')}")
                print("-" * 20)
        else:
            print("\nNo jobs found for the extracted skills.")
    else:
        print("\nCould not extract any skills from the resume.")


if __name__ == "__main__":
    main()