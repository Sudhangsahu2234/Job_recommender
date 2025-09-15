import re
import string
from collections import Counter
from typing import Dict, List, Tuple
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import PorterStemmer
import textstat
import os
import requests

nltk.download('punkt_tab')

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class UniversalATSChecker:
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
       
        # Essential resume sections that ATS systems look for
        self.essential_sections = {
            'contact': ['contact', 'phone', 'email', 'address', 'linkedin'],
            'experience': ['experience', 'work', 'employment', 'career', 'professional'],
            'education': ['education', 'degree', 'university', 'college', 'school'],
            'skills': ['skills', 'technical', 'competencies', 'expertise', 'abilities'],
            'summary': ['summary', 'objective', 'profile', 'about']
        }
       
        # Common action verbs that indicate strong experience descriptions
        self.action_verbs = [
            'achieved', 'managed', 'led', 'developed', 'created', 'implemented',
            'improved', 'increased', 'reduced', 'optimized', 'designed', 'built',
            'collaborated', 'coordinated', 'supervised', 'trained', 'analyzed',
            'executed', 'delivered', 'established', 'maintained', 'organized'
        ]
       
        # File format compatibility scores
        self.format_scores = {
            '.pdf': 100,
            '.docx': 95,
            '.doc': 80,
            '.txt': 60,
            '.rtf': 70,
            '.html': 50,
            '.jpg': 20,
            '.png': 20,
            '.gif': 15
        }
   
    def extract_text_from_file(self, file_path: str) -> str:
        try:
            if file_path.lower().endswith('.pdf'):
                try:
                    import pdfplumber
                    text = ""
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            text += page_text
                            if page.annots:
                                for annot in page.annots:
                                    uri = annot.get("uri") or annot.get("A", {}).get("URI")
                                    if uri:
                                        text += f"\n{uri}"
                    return text
                except ImportError:
                    return "Install pdfplumber: pip install pdfplumber"

            elif file_path.lower().endswith('.docx'):
                try:
                    import docx
                    doc = docx.Document(file_path)
                    text_parts = []
                    for para in doc.paragraphs:
                        text_parts.append(para.text)
                        for run in para.runs:
                            if "HYPERLINK" in run._element.xml:
                                match = re.search(r'HYPERLINK \"(.*?)\"', run._element.xml)
                                if match:
                                    text_parts.append(match.group(1))
                    return '\n'.join(text_parts)
                except ImportError:
                    return "Install python-docx: pip install python-docx"

            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    return file.read()

        except Exception as e:
            return f"Error reading file: {str(e)}"
   
    def check_contact_information(self, text: str) -> Dict:
        score = 0
        found_elements = []
        missing_elements = []

        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            score += 25
            found_elements.append('Email')
        else:
            missing_elements.append('Email address')

        # Phone pattern (various formats)
        phone_patterns = [
            r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}'
        ]
        phone_found = any(re.search(pattern, text) for pattern in phone_patterns)
        if phone_found:
            score += 20
            found_elements.append('Phone')
        else:
            missing_elements.append('Phone number')

        # Improved LinkedIn pattern
        linkedin_pattern = r'linkedin\.com/in/[\w-]+'

        if re.search(linkedin_pattern, text.lower()):
            score += 15
            found_elements.append('LinkedIn')
        else:
            missing_elements.append('LinkedIn profile')

        # Address/Location (city, state)
        location_patterns = [
            r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b',
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s*[A-Z]{2}\b'
        ]
        location_found = any(re.search(pattern, text) for pattern in location_patterns)
        if location_found:
            score += 10
            found_elements.append('Location')

        # Name detection from top lines
        lines = text.strip().split('\n')[:3]
        name_found = any(len(line.split()) >= 2 and
                        all(word.replace('-', '').replace("'", "").isalpha()
                            for word in line.split()[:3]) for line in lines)
        if name_found:
            score += 30
            found_elements.append('Name')
        else:
            missing_elements.append('Full name')

        return {
            'contact_score': score,
            'found_elements': found_elements,
            'missing_elements': missing_elements
        }

   
    def check_resume_sections(self, text: str) -> Dict:
        """Check for essential resume sections"""
        text_lower = text.lower()
        score = 0
        found_sections = []
        missing_sections = []
       
        for section_name, keywords in self.essential_sections.items():
            section_found = any(keyword in text_lower for keyword in keywords)
            if section_found:
                score += 20
                found_sections.append(section_name.title())
            else:
                missing_sections.append(section_name.title())
       
        return {
            'sections_score': score,
            'found_sections': found_sections,
            'missing_sections': missing_sections
        }
   
    def check_content_quality(self, text: str) -> Dict:
        score = 100
        issues = []
        strengths = []

        words = text.split()
        word_count = len(words)

        if word_count < 200:
            score -= 20
            issues.append("Resume is too short (under 200 words)")
        elif word_count > 2000:
            score -= 10
            issues.append("Resume may be too long (over 2000 words)")
        else:
            strengths.append(f"Good length ({word_count} words)")

        # Enhanced quantified achievement detection
        quantified_achievements = 0
        sentences = sent_tokenize(text)

        # Keywords and a more lenient number pattern
        impact_keywords = [
            "increased", "reduced", "grew", "boosted", "saved", "cut",
            "improved", "led", "managed", "achieved", "built", "developed",
            "created", "optimized", "generated", "scaled", "delivered"
        ]

        # Flexible number pattern
        number_regex = r"\b\d+(?:[,.]\d+)?\s*(%|percent|\$|k|K|m|M|million|thousand)?\b"

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(verb in sentence_lower for verb in impact_keywords) and re.search(number_regex, sentence_lower):
                quantified_achievements += 1


        if quantified_achievements >= 3:
            strengths.append("Contains quantified achievements")
        elif quantified_achievements >= 1:
            score -= 5
            issues.append("Could use more quantified achievements")
        else:
            score -= 15
            issues.append("Lacks quantified achievements (numbers, percentages)")

        # Action verbs check
        text_lower = text.lower()
        action_verb_count = sum(1 for verb in self.action_verbs if verb in text_lower)

        if action_verb_count >= 5:
            strengths.append("Uses strong action verbs")
        elif action_verb_count >= 2:
            score -= 5
            issues.append("Could use more action verbs")
        else:
            score -= 10
            issues.append("Lacks strong action verbs")

        # Readability
        try:
            readability = textstat.flesch_reading_ease(text)
            if readability >= 60:
                strengths.append("Good readability score")
            elif readability >= 30:
                score -= 5
                issues.append("Text could be more readable")
            else:
                score -= 10
                issues.append("Text is difficult to read")
        except:
            readability = "Unable to calculate"

        # Excessive special characters
        special_chars = len(re.findall(r'[^\w\s.-]', text))
        if special_chars / len(text) > 0.1:
            score -= 15
            issues.append("May contain excessive special characters/formatting")

        # Sentence structure
        sentences = sent_tokenize(text)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0

        if avg_sentence_length > 25:
            score -= 5
            issues.append("Sentences may be too long")
        elif avg_sentence_length < 8:
            score -= 5
            issues.append("Sentences may be too short")

        return {
            'content_score': max(0, score),
            'word_count': word_count,
            'quantified_achievements': quantified_achievements,
            'action_verbs_found': action_verb_count,
            'readability_score': readability,
            'issues': issues,
            'strengths': strengths
        }

   
    def check_formatting_compatibility(self, text: str, filename: str = "") -> Dict:
        """Check formatting for ATS compatibility"""
        score = 100
        issues = []
        recommendations = []
       
        # File format check
        if filename:
            file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
            format_score = self.format_scores.get(file_ext, 50)
           
            if format_score < 70:
                issues.append(f"File format {file_ext} may not be ATS-friendly")
                recommendations.append("Use PDF or DOCX format")
            elif format_score >= 95:
                pass  # No issues
            else:
                recommendations.append("PDF or DOCX formats are more ATS-friendly")
       
        # Check for tables/columns (indicated by excessive spacing)
        lines = text.split('\n')
        complex_formatting = sum(1 for line in lines if '\t' in line or '  ' * 3 in line)
       
        if complex_formatting > len(lines) * 0.3:
            score -= 15
            issues.append("May contain complex formatting (tables/columns)")
            recommendations.append("Use simple formatting without tables")
       
        # Check for unusual characters
        unusual_chars = re.findall(r'[^\w\s.,;:()\-@/]', text)
        if len(unusual_chars) > 10:
            score -= 10
            issues.append("Contains unusual characters that may cause parsing issues")
            recommendations.append("Remove special symbols and fancy formatting")
       
        # Check for proper spacing
        double_spaces = text.count('  ')
        if double_spaces > len(text.split()) * 0.1:
            score -= 5
            issues.append("Inconsistent spacing detected")
            recommendations.append("Use consistent single spacing")
       
        return {
            'formatting_score': max(0, score),
            'issues': issues,
            'recommendations': recommendations
        }
   
    def calculate_overall_ats_score(self, resume_text: str, filename: str = "") -> Dict:
        """Calculate comprehensive ATS score for any resume"""
       
        # Run all checks
        contact_results = self.check_contact_information(resume_text)
        sections_results = self.check_resume_sections(resume_text)
        content_results = self.check_content_quality(resume_text)
        formatting_results = self.check_formatting_compatibility(resume_text, filename)
       
        # Calculate weighted overall score
        # Contact Info: 25%, Sections: 25%, Content Quality: 35%, Formatting: 15%
        overall_score = (
            (contact_results['contact_score'] * 0.25) +
            (sections_results['sections_score'] * 0.25) +
            (content_results['content_score'] * 0.35) +
            (formatting_results['formatting_score'] * 0.15)
        )
       
        # Compile all recommendations
        all_recommendations = []
       
        if contact_results['missing_elements']:
            all_recommendations.append(f"Add missing contact info: {', '.join(contact_results['missing_elements'])}")
       
        if sections_results['missing_sections']:
            all_recommendations.append(f"Include these sections: {', '.join(sections_results['missing_sections'])}")
       
        all_recommendations.extend(content_results['issues'])
        all_recommendations.extend(formatting_results['recommendations'])
       
        # Determine ATS compatibility level
        if overall_score >= 85:
            compatibility = "Excellent - Highly ATS Compatible"
            emoji = "🟢"
        elif overall_score >= 70:
            compatibility = "Good - ATS Compatible with minor improvements"
            emoji = "🟡"
        elif overall_score >= 50:
            compatibility = "Fair - Needs improvements for better ATS compatibility"
            emoji = "🟠"
        else:
            compatibility = "Poor - Major improvements needed for ATS compatibility"
            emoji = "🔴"
       
        return {
            'overall_score': round(overall_score, 1),
            'compatibility_level': compatibility,
            'emoji': emoji,
            'detailed_scores': {
                'contact_information': contact_results['contact_score'],
                'resume_sections': sections_results['sections_score'],
                'content_quality': content_results['content_score'],
                'formatting': formatting_results['formatting_score']
            },
            'analysis_details': {
                'contact': contact_results,
                'sections': sections_results,
                'content': content_results,
                'formatting': formatting_results
            },
            'recommendations': all_recommendations[:8],  # Top 8 recommendations
            'strengths': content_results['strengths']
        }
   
    def generate_detailed_report(self, analysis_results: Dict) -> str:
        """Generate a comprehensive ATS report"""
        report = []
        report.append("=" * 60)
        report.append("ATS RESUME COMPATIBILITY REPORT")
        report.append("=" * 60)
       
        # Overall Score
        score = analysis_results['overall_score']
        compatibility = analysis_results['compatibility_level']
        emoji = analysis_results['emoji']
       
        report.append(f"\nOVERALL ATS SCORE: {score}/100")
        report.append(f"   {compatibility}")
        report.append("")
       
        # Detailed Breakdown
        report.append("DETAILED SCORE BREAKDOWN:")
        report.append("-" * 40)
        scores = analysis_results['detailed_scores']
        report.append(f"Contact Information:  {scores['contact_information']}/100")
        report.append(f"Resume Sections:      {scores['resume_sections']}/100")
        report.append(f"Content Quality:      {scores['content_quality']}/100")
        report.append(f"Formatting:           {scores['formatting']}/100")
        report.append("")
       
        # Strengths
        if analysis_results['strengths']:
            report.append("STRENGTHS:")
            for strength in analysis_results['strengths']:
                report.append(f"   • {strength}")
            report.append("")

        # Recommendations
        if analysis_results['recommendations']:
            report.append("IMPROVEMENT RECOMMENDATIONS:")
            for i, rec in enumerate(analysis_results['recommendations'], 1):
                report.append(f"   {i}. {rec}")
            report.append("")

        # Contact Information Details
        contact_details = analysis_results['analysis_details']['contact']
        report.append("CONTACT INFORMATION ANALYSIS:")
        if contact_details['found_elements']:
            report.append(f"   Found: {', '.join(contact_details['found_elements'])}")
        if contact_details['missing_elements']:
            report.append(f"   Missing: {', '.join(contact_details['missing_elements'])}")
        report.append("")

        # Resume Sections Details
        sections_details = analysis_results['analysis_details']['sections']
        report.append("RESUME SECTIONS ANALYSIS:")
        if sections_details['found_sections']:
            report.append(f"   Found: {', '.join(sections_details['found_sections'])}")
        if sections_details['missing_sections']:
            report.append(f"   Missing: {', '.join(sections_details['missing_sections'])}")
        report.append("")

        # Content Quality Details
        content_details = analysis_results['analysis_details']['content']
        report.append("CONTENT ANALYSIS:")
        report.append(f"   • Word Count: {content_details['word_count']}")
        report.append(f"   • Quantified Achievements: {content_details['quantified_achievements']}")
        report.append(f"   • Action Verbs Used: {content_details['action_verbs_found']}")
        report.append(f"   • Readability Score: {content_details['readability_score']}")
        report.append("")

        report.append("=" * 60)
        report.append("TIP: ATS systems prioritize clear structure, relevant keywords,")
        report.append("    and standard formatting. Focus on these areas for improvement!")
        report.append("=" * 60)
       
        return "\n".join(report)

def get_job_links(location, keywords=None):
    url = "https://jsearch.p.rapidapi.com/search"
    querystring = {"location": location}
    if keywords:
        querystring["query"] = keywords

    headers = {
        "X-RapidAPI-Key": "YOUR_RAPIDAPI_KEY",
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code == 200:
        jobs = response.json().get("data", [])
        return [job["job_apply_link"] for job in jobs[:5]]  # Return top 5 job links
    else:
        return []

# Main function for easy usage
def main():
    checker = UniversalATSChecker()
    
    print(" Universal ATS Resume Checker")
    print("=" * 40)
    
    file_path = 'Sample_data.pdf'  # You may want to make this dynamic
    resume_text = checker.extract_text_from_file(file_path)
    results = checker.calculate_overall_ats_score(resume_text, file_path)
    report = checker.generate_detailed_report(results)
    print(report)

    # Extract location from contact analysis
    contact_info = results.get('analysis_details', {}).get('contact', {})
    found_elements = contact_info.get('found_elements', [])
    location = None
    if 'Location' in found_elements:
        # Try to extract the actual location string from the resume text
        # Use the same patterns as in check_contact_information
        location_patterns = [
            r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b',
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s*[A-Z]{2}\b'
        ]
        for pattern in location_patterns:
            match = re.search(pattern, resume_text)
            if match:
                location = match.group(0)
                break
    if not location:
        print("\n[!] Location not found in resume. Skipping job search.")
        return

    print(f"\nSearching for jobs in: {location}")
    job_links = get_job_links(location)
    if job_links:
        print("\nTop Job Links:")
        for i, link in enumerate(job_links, 1):
            print(f"  {i}. {link}")
    else:
        print("No job links found for the extracted location.")

if __name__ == "__main__":
    main()

