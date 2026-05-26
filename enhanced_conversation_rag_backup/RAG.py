import os   
import pandas as pd 
import numpy as np
import pickle
import hashlib
import json
import google.generativeai as genai 
from dotenv import load_dotenv
from datetime import datetime
import csv
import re
import math
from collections import Counter
from openpyxl import load_workbook

# ===============================================
# USER CONFIGURATION - EDIT THESE PATHS
# ===============================================

# 1. PUT YOUR STUDENT DATA EXCEL/CSV FILE PATH HERE:
STUDENT_CSV_PATH = "/Users/partners/Desktop/Helloivy_dev/conv_rag/DATA/MR2614_PG_Student_Brainstorming_Form_V1  (1).xlsx"

# 2. Knowledge base CSV file path (essays database):
KNOWLEDGE_CSV_PATH = "/Users/partners/Desktop/Helloivy_dev/conv_rag/BS Notes, Snyopsis & Ivy Questions(UG_Commonapp_Question).csv"

# ===============================================

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY not found. Please set it in your .env file.")
genai.configure(api_key=api_key)

# Basic RAG system using word similarity
class BasicRAG:
    def __init__(self):
        self.documents = []
        self.doc_word_counts = []
        
    def _preprocess_text(self, text):
        """Basic text preprocessing"""
        # Convert to lowercase and remove punctuation
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        # Split into words and remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall', 'this', 'that', 'these', 'those'}
        words = [word for word in text.split() if word and len(word) > 2 and word not in stop_words]
        return words
    
    def _cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two word count vectors"""
        # Get all unique words from both vectors
        all_words = set(vec1.keys()) | set(vec2.keys())
        
        # Create vectors
        v1 = [vec1.get(word, 0) for word in all_words]
        v2 = [vec2.get(word, 0) for word in all_words]
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(v1, v2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(a * a for a in v2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def load_documents(self, documents):
        """Load and preprocess documents"""
        self.documents = documents
        self.doc_word_counts = []
        
        for doc in documents:
            words = self._preprocess_text(doc)
            word_count = Counter(words)
            self.doc_word_counts.append(word_count)
    
    def search(self, query, top_k=3):
        """Search for most relevant documents"""
        if not self.documents:
            return []
        
        query_words = self._preprocess_text(query)
        query_word_count = Counter(query_words)
        
        # Calculate similarities
        similarities = []
        for i, doc_word_count in enumerate(self.doc_word_counts):
            sim = self._cosine_similarity(query_word_count, doc_word_count)
            similarities.append((i, sim))
        
        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, sim in similarities[:top_k]:
            if sim > 0:  # Only return docs with some similarity
                results.append(self.documents[i])
        
        return results

# Initialize RAG system
rag_system = BasicRAG()
print("✅ Using basic RAG system compatible with PyTorch 2.0.1")

# Convert Excel to JSON and clean up old files
def convert_excel_to_json(excel_path, json_path):
    """Convert Excel file to JSON format, delete old JSON if exists"""
    
    try:
        # Delete old temporary JSON file if it exists
        if os.path.exists(json_path):
            os.remove(json_path)
            print(f"Deleted old temporary file: {json_path}")
        
        # Check if Excel file exists
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        
        print(f"Converting Excel to JSON: {excel_path}")
        
        # Read Excel file
        try:
            df = pd.read_excel(excel_path, engine='openpyxl')
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            raise
        
        if df.empty:
            raise ValueError("Excel file is empty")
        
        # Convert DataFrame to JSON format
        json_data = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "source_file": excel_path,
            "total_rows": len(df),
            "columns": df.columns.tolist(),
            "data": df.to_dict('records')  # Convert all rows to list of dictionaries
        }
        
        # Save as JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"Excel converted to JSON successfully: {json_path}")
        print(f"Total rows: {len(df)}, Columns: {len(df.columns)}")
        
        return json_data
        
    except Exception as e:
        print(f"Error converting Excel to JSON: {e}")
        return None

# Load student profile from JSON (converted from Excel)
def load_student_profile_from_json(json_data):
    """Load student profile dynamically from JSON data (converted from Excel)"""
    
    try:
        if not json_data or 'data' not in json_data:
            raise ValueError("Invalid JSON data provided")
        
        print(f"Loading student profile from JSON data")
        print(f"Source: {json_data.get('source_file', 'Unknown')}")
        print(f"Total rows: {json_data.get('total_rows', 0)}")
        
        # Get all data rows
        all_data = json_data['data']
        if not all_data:
            raise ValueError("No data found in JSON")

        # Base student info dictionary - NO hardcoded defaults
        student_info = {
            'name': '',
            'lastname': '',
            'email': '',
            'degree': '',
            'university': '',
            'gpa': '',
            'company_name': '',
            'job_title': '',
            'leadership': '',
            'school_12th': '',
            'work_experience': '',
            'citizenship': '',
            'current_location': '',
            'birth_place': '',
            'father_profession': '',
            'mother_profession': '',
        }
        
        # Store ALL JSON data for complete context
        student_info['raw_json_data'] = all_data
        
        # Extract key information from the key-value structure (Unnamed: 1 = key, Unnamed: 2 = value)
        if all_data:
            # Process all rows to extract key-value pairs
            extracted_data = {}
            for row in all_data:
                if 'Unnamed: 1' in row and 'Unnamed: 2' in row:
                    key = str(row['Unnamed: 1']).strip().lower() if row['Unnamed: 1'] else ''
                    value = str(row['Unnamed: 2']).strip() if row['Unnamed: 2'] else ''
                    
                    if key and value and value != 'nan':
                        # Clean the key by removing colons and extra spaces
                        clean_key = key.replace(':', '').strip()
                        extracted_data[clean_key] = value
            
            # Map extracted keys to student info fields
            field_mappings = {
                'name': ['firstname', 'first name', 'name'],
                'lastname': ['lastname', 'last name', 'surname'],
                'email': ['email', 'email address', 'mail'],
                'degree': ['degree', 'qualification', 'education', 'course'],
                'university': ['university', 'college', 'institution'],
                'gpa': ['gpa', 'grade', 'percentage', 'marks', 'cgpa'],
                'company_name': ['company', 'organization', 'workplace', 'current company'],
                'job_title': ['job title', 'position', 'role', 'designation', 'current position'],
                'work_experience': ['work experience', 'professional experience', 'experience'],
                'leadership': ['leadership', 'leadership experience', 'leadership positions'],
                'citizenship': ['citizenship', 'nationality'],
                'current_location': ['current location', 'location', 'city'],
                'birth_place': ['city of birth', 'place of birth', 'birthplace']
            }
            
            # Extract fields from the key-value pairs
            for field, possible_keys in field_mappings.items():
                for key_pattern in possible_keys:
                    for extracted_key, extracted_value in extracted_data.items():
                        if key_pattern in extracted_key:
                            student_info[field] = extracted_value
                            break
                    if student_info[field]:  # Break outer loop if found
                        break
            
            # Store the complete extracted data for context
            student_info['extracted_data'] = extracted_data
        
        # Set default name if not found
        if not student_info['name']:
            student_info['name'] = 'Student'
        
        print(f"Student profile loaded from JSON data")
        print(f"   Name: {student_info['name']}")
        print(f"   Email: {student_info['email']}")
        print(f"   Degree: {student_info['degree']}")
        print(f"   Total data rows available: {len(all_data)}")
        
        return student_info
        
    except Exception as e:
        print(f"Error loading student profile from JSON: {e}")
        # Return minimal profile without hardcoded data
        return {
            'name': 'Student',
            'lastname': '',
            'email': '',
            'degree': '',
            'university': '',
            'gpa': '',
            'company_name': '',
            'job_title': '',
            'leadership': '',
            'school_12th': '',
            'work_experience': '',
            'citizenship': '',
            'current_location': '',
            'birth_place': '',
            'father_profession': '',
            'mother_profession': '',
        }

# Load student profile from Excel/CSV file  
def load_student_profile_from_csv(file_path):
    """Load student profile from Excel (.xlsx) or CSV file"""
    
    try:
        if not file_path:
            raise ValueError("File path is required")
        
        print(f"Loading student profile from: {file_path}")
        
        # Check file extension to determine processing method
        if file_path.lower().endswith('.xlsx'):
            # Handle Excel file
            print("Excel file detected - converting to JSON...")
            temp_json_path = "/Users/partners/Desktop/Helloivy_dev/conv_rag/temp_student_data.json"
            json_data = convert_excel_to_json(file_path, temp_json_path)
            
            if json_data:
                return load_student_profile_from_json(json_data)
            else:
                raise ValueError("Failed to convert Excel file")
        
        else:
            # Handle CSV file (existing logic)
            print("CSV file detected - processing...")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"CSV file not found: {file_path}")
            
            # Try different encodings for CSV
            df = None
            encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
                raise ValueError("Unable to read CSV file with any encoding")
            
            if df.empty:
                raise ValueError("CSV file is empty")
            
            # Base student info dictionary - NO hardcoded defaults
            student_info = {
                'name': '',
                'lastname': '',
                'email': '',
                'degree': '',
                'university': '',
                'gpa': '',
                'company_name': '',
                'job_title': '',
                'leadership': '',
                'school_12th': '',
                'work_experience': '',
                'citizenship': '',
                'current_location': '',
                'birth_place': '',
                'father_profession': '',
                'mother_profession': '',
            }
            
            # Handle special CSV format where data is in key-value rows
            # Check if this is a key-value pair format (like your CSV)
            is_key_value_format = False
            for idx, row in df.iterrows():
                if pd.notna(row.iloc[1]) and ':' in str(row.iloc[1]):
                    is_key_value_format = True
                    break
            
            if is_key_value_format:
                # Extract data from key-value pair format
                for idx, row in df.iterrows():
                    if len(row) >= 3 and pd.notna(row.iloc[1]) and pd.notna(row.iloc[2]):
                        key = str(row.iloc[1]).strip().lower()
                        value = str(row.iloc[2]).strip()
                        
                        if value and value != 'nan':
                            # Map keys to student info fields
                            if 'firstname' in key or 'first name' in key:
                                student_info['name'] = value
                            elif 'lastname' in key or 'last name' in key or 'surname' in key:
                                student_info['lastname'] = value
                            elif 'email' in key:
                                student_info['email'] = value
                            elif 'degree' in key or 'qualification' in key:
                                student_info['degree'] = value
                            elif 'university' in key or 'college' in key or 'institution' in key:
                                student_info['university'] = value
                            elif 'gpa' in key or 'grade' in key or 'percentage' in key or 'marks' in key:
                                student_info['gpa'] = value
                            elif 'company' in key or 'organization' in key or 'workplace' in key:
                                student_info['company_name'] = value
                            elif 'job' in key or 'position' in key or 'role' in key or 'designation' in key:
                                student_info['job_title'] = value
                            elif 'leadership' in key or 'positions held' in key:
                                student_info['leadership'] = value
                            elif 'school' in key and ('12th' in key or 'high' in key):
                                student_info['school_12th'] = value
                            elif 'work' in key and 'experience' in key:
                                student_info['work_experience'] = value
                            elif 'citizenship' in key or 'nationality' in key:
                                student_info['citizenship'] = value
                            elif 'location' in key or 'address' in key:
                                student_info['current_location'] = value
                            elif 'birth' in key and 'place' in key:
                                student_info['birth_place'] = value
                            elif 'father' in key and ('profession' in key or 'job' in key or 'occupation' in key):
                                student_info['father_profession'] = value
                            elif 'mother' in key and ('profession' in key or 'job' in key or 'occupation' in key):
                                student_info['mother_profession'] = value
            
            else:
                # Handle traditional column-based format
                student_row = df.iloc[0]
            
            # Map CSV columns to student info fields dynamically
            column_mappings = {
                'name': ['name', 'student_name', 'full_name', 'first_name', 'firstname'],
                'lastname': ['lastname', 'last_name', 'surname'],
                'email': ['email', 'email_address', 'mail'],
                'degree': ['degree', 'qualification', 'education', 'course'],
                'university': ['university', 'college', 'institution', 'school'],
                'gpa': ['gpa', 'grade', 'percentage', 'marks', 'cgpa'],
                'company_name': ['company', 'company_name', 'organization', 'workplace', 'work_experience'],
                'job_title': ['job_title', 'position', 'role', 'designation'],
                'leadership': ['leadership', 'leadership_experience', 'positions_held'],
                'school_12th': ['school_12th', '12th_school', 'high_school'],
                'work_experience': ['work_experience', 'experience', 'professional_experience'],
                'citizenship': ['citizenship', 'nationality', 'country'],
                'current_location': ['current_location', 'location', 'address'],
                'birth_place': ['birth_place', 'birthplace', 'place_of_birth'],
                'father_profession': ['father_profession', 'father_job', 'father_occupation'],
                'mother_profession': ['mother_profession', 'mother_job', 'mother_occupation']
            }
            
            # Extract data from CSV columns dynamically
            df_columns_lower = [col.lower().strip().replace(' ', '_') for col in df.columns]
            
            for field, possible_columns in column_mappings.items():
                for col_name in possible_columns:
                    col_name_normalized = col_name.lower().strip().replace(' ', '_')
                    if col_name_normalized in df_columns_lower:
                        col_index = df_columns_lower.index(col_name_normalized)
                        actual_col_name = df.columns[col_index]
                        value = student_row[actual_col_name]
                        
                        # Clean and set the value
                        if pd.notna(value) and str(value).strip():
                            student_info[field] = str(value).strip()
                            break
            
            # Set default name if not found
            if not student_info['name']:
                student_info['name'] = 'Student'
            
            print(f"Student profile loaded dynamically")
            print(f"   Name: {student_info['name']}")
            print(f"   Email: {student_info['email']}")
            print(f"   Degree: {student_info['degree']}")
            print(f"   GPA: {student_info['gpa']}")
            print(f"   Company: {student_info['company_name']}")
            print(f"   Job Title: {student_info['job_title']}")
            print(f"   Leadership: {student_info['leadership']}")
            
            return student_info
        
    except Exception as e:
        print(f"⚠️ Error loading student profile from CSV: {e}")
        # Return minimal profile without hardcoded data
        return {
            'name': 'Student',
            'lastname': '',
            'email': '',
            'degree': '',
            'university': '',
            'gpa': '',
            'company_name': '',
            'job_title': '',
            'leadership': '',
            'school_12th': '',
            'work_experience': '',
            'citizenship': '',
            'current_location': '',
            'birth_place': '',
            'father_profession': '',
            'mother_profession': '',
        }

# Load student profile from user-specified CSV
if not STUDENT_CSV_PATH:
    print("⚠️  ATTENTION: You must specify your student data CSV file path!")
    print("   Edit the STUDENT_CSV_PATH variable at the top of this file")
    print("   Example: STUDENT_CSV_PATH = '/path/to/your/student_data.csv'")
    student_profile = {
        'name': 'Student',
        'lastname': '',
        'email': '',
        'degree': '',
        'university': '',
        'gpa': '',
        'company_name': '',
        'job_title': '',
        'leadership': '',
        'school_12th': '',
        'work_experience': '',
        'citizenship': '',
        'current_location': '',
        'birth_place': '',
        'father_profession': '',
        'mother_profession': '',
    }
else:
    print(f"📄 Loading student data from: {STUDENT_CSV_PATH}")
    student_profile = load_student_profile_from_csv(STUDENT_CSV_PATH)

# Load CSV data for RAG (knowledge base)
csv_path = KNOWLEDGE_CSV_PATH
try:
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError("CSV file is empty")
    
    # Select relevant columns for context
    text_columns = df.columns.tolist()
    docs = df[text_columns].fillna('').astype(str).agg(" ".join, axis=1).tolist()
    
    # Filter out empty documents
    docs = [doc.strip() for doc in docs if doc.strip()]
    
    # Load documents into RAG system
    rag_system.load_documents(docs)
    
    print(f"✅ Loaded {len(docs)} documents for RAG")
    
except FileNotFoundError:
    print(f"⚠️ CSV file not found: {csv_path}")
    rag_system.load_documents([])  # Initialize with empty documents
except Exception as e:
    print(f"⚠️ Error loading CSV: {e}")
    rag_system.load_documents([])  # Initialize with empty documents

# Cache system for reducing token costs
cache_file = "/Users/partners/Desktop/Helloivy_dev/RAG_trial/question_cache.json"

def load_cache():
    """Load existing cache or create empty one"""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache_data):
    """Save cache to disk"""
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def create_cache_key(essay_topic, college_name, word_limit, major, student_name="Aaron"):
    """Create unique cache key including student profile"""
    # Normalize inputs for consistent caching
    normalized_data = {
        'topic': essay_topic.lower().strip(),
        'college': college_name.lower().strip(),
        'word_limit': str(word_limit),
        'major': major.lower().strip(),
        'student': student_name.lower().strip()
    }
    # Create hash of the normalized data
    cache_string = json.dumps(normalized_data, sort_keys=True)
    return hashlib.md5(cache_string.encode()).hexdigest()

def estimate_tokens(text):
    """Estimate token count (rough approximation: ~4 chars per token)"""
    return len(text) // 4

def generate_with_gemini(prompt, model_name="gemini-1.5-flash", temperature=0.7, max_tokens=1000):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                candidate_count=1,
            ),
        )
        if response.candidates and response.candidates[0].content.parts:
            generated_text = response.candidates[0].content.parts[0].text
            
            # Calculate token usage
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(generated_text)
            
            return generated_text, input_tokens, output_tokens
        else:
            return "❌ No response generated from Gemini.", 0, 0
    except Exception as e:
        return f"❌ Error with Gemini API: {str(e)}", 0, 0

def create_student_context_string(student_profile):
    """Create a formatted string of student context for the prompt"""
    if not student_profile:
        return "No student profile available."
    
    context = f"""STUDENT PROFILE - {student_profile['name']}:

KEY PERSONAL DETAILS (USE THESE EXACT VALUES):
• Name: {student_profile['name']}
• Academic Background: {student_profile['degree']} (GPA: {student_profile['gpa']})
• Professional Experience: {student_profile['job_title']} at {student_profile['company_name']}
• Work Experience: {student_profile['work_experience']}
• Leadership Experience: {student_profile['leadership']}
• Educational Background: 12th from {student_profile['school_12th']}
• Citizenship: {student_profile['citizenship']}
• Email: {student_profile['email']}

IMPORTANT: When writing questions, use these EXACT values - not placeholders!
For example: Use "Bangalore" not "[location]", use "Engineer" not "[father's profession]", use actual company name not "[Company Name]"
CRITICAL: Never use empty values or placeholders like [] in questions. If a field is empty, don't reference it or find alternative phrasing.

ADDITIONAL PROFILE DATA:"""
    
    # Add other relevant profile data from raw_profile
    if 'raw_profile' in student_profile:
        key_fields = [
            'Job Title', 'Your Responsibilities (In detail)', 'Top 3 achievements', 
            'Any red flags/ grade below C:', 'Reason for Leaving',
            'School Name (10th grade):', 'School Name (11th grade):', 
            'Mention individual subject + grades/scores:'
        ]
        
        for field in key_fields:
            if field in student_profile['raw_profile']:
                value = student_profile['raw_profile'][field]
                if value and str(value).strip():
                    context += f"\n• {field}: {value}"
    
    return context

def generate_single_question(essay_topic, college_name, major, word_limit, question_number, conversation_history, top_k=3):
    """Generate a single question based on previous context and user responses"""
    
    # Build query from basic info
    query = f"Essay Topic/Prompt: {essay_topic}\nCollege: {college_name}\nMajor: {major}\nWord Limit: {word_limit} words\n"
    
    # Get relevant context using BasicRAG system
    try:
        relevant_docs = rag_system.search(query, top_k)
        context = "\n".join(relevant_docs) if relevant_docs else ""
    except Exception as e:
        print(f"⚠️ Error retrieving context: {e}")
        context = ""
    
    # Create student context
    student_context = create_student_context_string(student_profile)
    
    # Build conversation history context
    history_context = ""
    if conversation_history:
        history_context = "\nPREVIOUS QUESTIONS AND ANSWERS:\n"
        for i, qa in enumerate(conversation_history, 1):
            history_context += f"Question {i}: {qa['question']}\nAnswer: {qa['answer']}\n\n"
    
    # Determine question guidelines based on word limit
    def get_question_guidelines(limit):
        try:
            limit_num = int(limit)
            if limit_num <= 500:
                return {
                    "depth": "focused and detailed but concise",
                    "style": "ask for specific examples, moments, or experiences",
                    "guidance": "Questions should help extract concrete stories that can be told in 500 words"
                }
            elif limit_num <= 1000:
                return {
                    "depth": "detailed and thorough",
                    "style": "ask for deeper reflection and multiple aspects",
                    "guidance": "Questions can explore context, impact, and lessons learned"
                }
            else:
                return {
                    "depth": "comprehensive and analytical", 
                    "style": "ask for detailed narratives with reflection and analysis",
                    "guidance": "Questions can explore complex themes, multiple perspectives, and deep insights"
                }
        except (ValueError, TypeError):
            return {
                "depth": "detailed and thorough",
                "style": "ask for deeper reflection and multiple aspects",
                "guidance": "Questions can explore context, impact, and lessons learned"
            }
    
    guidelines = get_question_guidelines(word_limit)
    
    # Build conversation history context and track themes
    history_context = ""
    previous_themes = set()
    if conversation_history:
        history_context = "\nPREVIOUS QUESTIONS AND ANSWERS:\n"
        for i, qa in enumerate(conversation_history, 1):
            history_context += f"Question {i}: {qa['question']}\nAnswer: {qa['answer']}\n\n"
            # Extract themes from previous questions to avoid repetition
            if 'motivation' in qa['question'].lower() or 'why' in qa['question'].lower():
                previous_themes.add('motivation')
            if 'challenge' in qa['question'].lower() or 'difficult' in qa['question'].lower():
                previous_themes.add('challenges')
            if 'goal' in qa['question'].lower() or 'future' in qa['question'].lower():
                previous_themes.add('goals')
            if 'experience' in qa['question'].lower() or 'moment' in qa['question'].lower():
                previous_themes.add('experiences')
            if 'learn' in qa['question'].lower() or 'skill' in qa['question'].lower():
                previous_themes.add('learning')
    
    # Define unique question approaches for each question number
    question_approaches = {
        1: {
            "focus": "Initial motivation/inspiration",
            "angle": "What sparked your interest in this specific topic/program",
            "blend": "Connect personal/academic background to essay topic discovery"
        },
        2: {
            "focus": "Specific experience/moment",
            "angle": "A defining experience that shaped your perspective on the essay topic",
            "blend": "Use work/academic experience to illustrate essay topic relevance"
        },
        3: {
            "focus": "Challenge/obstacle overcome",
            "angle": "How you navigated challenges related to the essay topic",
            "blend": "Connect leadership/work challenges to essay topic mastery"
        },
        4: {
            "focus": "Skills/knowledge gaps identified",
            "angle": "What you realized you need to learn/develop for essay topic success",
            "blend": "Bridge current capabilities with essay topic requirements"
        },
        5: {
            "focus": "Future vision/impact",
            "angle": "How you plan to apply essay topic learning in your future",
            "blend": "Connect career goals with essay topic outcomes"
        }
    }
    
    current_approach = question_approaches.get(question_number, question_approaches[1])

    # Get student's name for personalized conversation
    student_name = student_profile.get('name', 'Student')

    # Get specific user details for ultra-personalized questions
    user_company = student_profile.get('company_name', 'your current workplace')
    user_degree = student_profile.get('degree', 'your background')
    user_job_title = student_profile.get('job_title', 'your role')
    user_university = student_profile.get('university', 'your university')
    user_location = student_profile.get('current_location', 'your area')

    # Build ULTRA personalized conversation prompt
    prompt = (
        f"You are having a casual, friendly conversation with {student_name} as their personal college counselor. You know them well and are genuinely excited to help them craft their essay about '{essay_topic}' for {college_name}.\n\n"

        f"MAKE IT SUPER PERSONAL:\n"
        f"- ALWAYS start with 'Hey {student_name}!' or '{student_name},' in a natural way\n"
        f"- Reference specific details: {user_company}, {user_degree}, {user_job_title}, {user_location}\n"
        f"- Connect their personal story to {essay_topic}\n"
        f"- Ask about their actual experiences, not hypothetical scenarios\n"
        f"- Use their name 2-3 times in the question naturally\n"
        f"- Reference what you 'know' about them from their profile\n\n"

        f"STUDENT PROFILE TO USE:\n"
        f"Name: {student_name}\n"
        f"Company: {user_company}\n"
        f"Role: {user_job_title}\n"
        f"Education: {user_degree} from {user_university}\n"
        f"Location: {user_location}\n\n"

        f"ESSAY TARGET:\n"
        f"Topic: {essay_topic}\n"
        f"College: {college_name} - {major}\n"
        f"Word Limit: {word_limit} words\n\n"
        
        f"{student_context}\n\n"
        
        f"CONTEXT GUIDANCE:\n{context[:500]}\n\n"
        
        f"CONVERSATION SO FAR:\n{history_context}"
        
        f"AVOID THESE THEMES (already covered): {', '.join(previous_themes) if previous_themes else 'None'}\n\n"
        
        f"CONVERSATION RULES:\n"
        f"1. USE {student_name.upper()}'S NAME: Always include their name naturally in the conversation\n"
        f"2. CONVERSATIONAL STYLE: Write like you're talking to a friend, not conducting an interview\n"
        f"3. ESSAY TOPIC FOCUS: Connect everything back to '{essay_topic}' naturally\n"
        f"4. BUILD ON PREVIOUS ANSWERS: {('Reference what ' + student_name + ' shared before and ask follow-up questions') if question_number > 1 else ('Start the conversation by getting to know ' + student_name + ' better')}\n"
        f"5. PERSONAL CONTEXT: Use specific details from {student_name}'s background (company: {student_profile.get('company_name', 'N/A')}, degree: {student_profile.get('degree', 'N/A')})\n"
        f"6. FOLLOW-UP READY: Ask questions that naturally lead to follow-up conversations\n"
        f"7. ENCOURAGING TONE: Be supportive and show genuine interest in their story\n"
        f"8. LENGTH: 1-2 sentences, conversational length (20-40 words)\n\n"
        
        f"ULTRA-PERSONALIZED EXAMPLES:\n"
        f"Question 1: 'Hey {student_name}! I know you've been working at {user_company} as a {user_job_title}, and with your {user_degree} background from {user_university}, I'm really curious - what moment at work or in your studies made you realize {essay_topic} was your passion?'\n"
        f"Question 2: '{student_name}, I'm fascinated by your journey from {user_degree} to working at {user_company}. Can you tell me about a specific project or experience there that really sparked your interest in {essay_topic}?'\n"
        f"Question 3: 'You know, {student_name}, given your experience in {user_location} and at {user_company}, what's the biggest challenge you've seen in {essay_topic} that you want to help solve?'\n"
        f"Question 4: 'Hey {student_name}, I'm thinking about your background at {user_company} - how do you think your experience as a {user_job_title} gives you a unique perspective on {essay_topic}?'\n"
        f"Question 5: '{student_name}, looking at your path from {user_university} to {user_company}, where do you see yourself making the biggest impact in {essay_topic} in the next few years?'\n\n"

        f"MUST AVOID (Generic/Formal):\n"
        f"❌ 'Hey! I'm here to help you brainstorm...'\n"
        f"❌ 'Based on your experiences, can you tell me...'\n"
        f"❌ 'Let's start by understanding your connection...'\n"
        f"✅ 'Hey {student_name}! I know you work at {user_company}...'\n"
        f"✅ '{student_name}, with your {user_degree} background and experience at {user_company}...'\n"
        f"✅ 'You know, {student_name}, I'm thinking about your journey from {user_university}...'\n\n"
        
        f"Generate exactly ONE conversational question that:\n"
        f"1. Uses {student_name}'s name naturally\n"
        f"2. Focuses on '{essay_topic}' as the main theme\n"
        f"3. References their personal background contextually (40% context from RAG, 60% from current profile)\n"
        f"4. Feels like a natural conversation, not an interview\n"
        f"5. Sets up potential follow-up questions based on their response\n\n"
    )

    # Add conversational reminders for different question numbers
    if question_number == 1:
        conversation_starter = f"CONVERSATION STARTER: This is your first question to {student_name}. Be warm, welcoming, and show genuine interest in getting to know them.\n\n"
        prompt += conversation_starter
    elif question_number > 1:
        follow_up_reminder = f"FOLLOW-UP CONVERSATION: This is question {question_number}. Reference what {student_name} shared before and build on it naturally. Use phrases like 'That's interesting...', 'I'm curious about...', or 'Tell me more about...'\n\n"
        prompt += follow_up_reminder

    prompt += f"Your question to {student_name}:"
    
    # Generate question using AI
    question, input_tokens, output_tokens = generate_with_gemini(prompt, max_tokens=100)
    
    return question.strip(), input_tokens, output_tokens

def generate_follow_up_question(essay_topic, student_name, last_question, last_answer, student_profile):
    """Generate a highly personalized follow-up question based on the user's response"""

    # Get user details for personalization
    user_company = student_profile.get('company_name', 'your workplace')
    user_degree = student_profile.get('degree', 'your background')
    user_job_title = student_profile.get('job_title', 'your role')
    user_location = student_profile.get('current_location', 'your area')

    prompt = (
        f"You're having an intimate, personal conversation with {student_name}, someone you know well. They just shared something meaningful about their essay on '{essay_topic}', and you want to dig deeper with genuine curiosity.\n\n"

        f"WHAT {student_name.upper()} JUST SHARED:\n"
        f"Your Question: {last_question}\n"
        f"{student_name}'s Answer: {last_answer}\n\n"

        f"THEIR PERSONAL CONTEXT:\n"
        f"- Works at: {user_company}\n"
        f"- Role: {user_job_title}\n"
        f"- Background: {user_degree}\n"
        f"- Location: {user_location}\n\n"

        f"ULTRA-PERSONAL FOLLOW-UP RULES:\n"
        f"- Start with '{student_name},' or 'That's amazing, {student_name}!' or 'Wow, {student_name}!'\n"
        f"- Pick out ONE specific detail they mentioned and ask about it\n"
        f"- Connect it to their work at {user_company} or their {user_degree} background if relevant\n"
        f"- Ask about their emotions, thoughts, or personal growth\n"
        f"- Reference their specific situation, not generic scenarios\n\n"

        f"PERSONALIZED FOLLOW-UP EXAMPLES:\n"
        f"- 'Wow, {student_name}! When you mention [specific thing they said], that reminds me of your work at {user_company} - how did that experience shape your thinking?'\n"
        f"- '{student_name}, that's incredible! I'm curious about that moment you described - what was going through your mind as someone with your {user_degree} background?'\n"
        f"- 'That's such a powerful story, {student_name}! Given your experience at {user_company}, how do you think that moment will influence your approach to {essay_topic}?'\n\n"

        f"Generate ONE deeply personal follow-up question (25-40 words) that shows you really heard what {student_name} shared:"
    )

    try:
        follow_up, input_tokens, output_tokens = generate_with_gemini(prompt, max_tokens=100)
        return follow_up.strip(), input_tokens, output_tokens
    except Exception as e:
        print(f"❌ Error generating follow-up: {e}")
        return f"That's really interesting, {student_name}! Can you tell me more about that experience?", 0, 0

def save_latest_conversation(user_data, conversation_history):
    """Save only the latest conversation to a separate file for structure generation"""
    latest_conversation_file = "/Users/partners/Desktop/Helloivy_dev/structure_rag/latest_conversation.json"
    
    # Prepare latest conversation data
    latest_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'student_name': student_profile['name'] if student_profile else "Unknown",
        'essay_topic': user_data.get('essay_topic', ''),
        'college_name': user_data.get('college_name', ''),
        'degree': user_data.get('degree', ''),
        'major': user_data.get('major', ''),
        'word_limit': user_data.get('word_limit', ''),
        'conversation': []
    }
    
    # Add Q&A pairs
    for qa in conversation_history:
        latest_data['conversation'].append({
            'question': qa['question'],
            'answer': qa['answer']
        })
    
    # Save as JSON (overwrite each time)
    try:
        with open(latest_conversation_file, 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Latest conversation saved to {latest_conversation_file}")
        return latest_conversation_file
    except Exception as e:
        print(f"❌ Error saving latest conversation: {e}")
        return None

def save_qa_to_csv(user_data, conversation_history, total_input_tokens, total_output_tokens):
    """Save user input, questions, answers, and token usage to CSV file"""
    output_file = "/Users/partners/Desktop/Helloivy_dev/conv_rag/op.csv"
    
    # Calculate token costs
    total_tokens = total_input_tokens + total_output_tokens
    
    # Prepare conversation data
    all_questions = []
    all_answers = []
    for qa in conversation_history:
        all_questions.append(qa['question'])
        all_answers.append(qa['answer'])
    
    # Prepare data for CSV
    student_name = student_profile['name'] if student_profile else "Unknown"
    row_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'student_name': student_name,
        'essay_topic': user_data.get('essay_topic', ''),
        'college_name': user_data.get('college_name', ''),
        'degree': user_data.get('degree', ''),
        'major': user_data.get('major', ''),
        'word_limit': user_data.get('word_limit', ''),
        'questions_asked': ' | '.join(all_questions),
        'user_answers': ' | '.join(all_answers),
        'num_questions': len(conversation_history),
        'input_tokens': total_input_tokens,
        'output_tokens': total_output_tokens,
        'total_tokens': total_tokens,
        'personalized': 'YES - Using student profile' if student_profile else 'NO',
        'session_type': 'Interactive Q&A'
    }
    
    # Check if file exists to determine if we need headers
    file_exists = os.path.exists(output_file)
    
    # Write to CSV
    with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'student_name', 'essay_topic', 'college_name', 'degree', 'major', 
                     'word_limit', 'questions_asked', 'user_answers', 'num_questions', 'input_tokens', 
                     'output_tokens', 'total_tokens', 'personalized', 'session_type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header if file is new
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(row_data)
    
    # Also save latest conversation for structure generation
    save_latest_conversation(user_data, conversation_history)
    
    print(f"✅ Interactive session data saved to {output_file}")
    print(f"💳 Total token usage: {total_input_tokens} input + {total_output_tokens} output = {total_tokens} total tokens")

def main():
    import sys
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Interactive College Essay Brainstorming Assistant")
    parser.add_argument("--essay-topic", help="Essay topic/prompt")
    parser.add_argument("--college", help="College name")
    parser.add_argument("--degree", help="Degree type (e.g., UG, MBA, MS)")
    parser.add_argument("--major", help="Major/field of interest")
    parser.add_argument("--word-limit", help="Word limit for essay")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode with defaults")
    args = parser.parse_args()
    
    print("\n🎓 Interactive College Essay Brainstorming Assistant 🎓")
    print("This tool generates personalized questions one by one, building context from your responses!\n")
    
    # Show student profile if loaded
    if student_profile:
        print(f"👤 Student Profile: {student_profile['name']}")
        print(f"📚 Academic: {student_profile['degree']} (GPA: {student_profile['gpa']})")
        print(f"🏢 Professional: {student_profile['job_title']} at {student_profile['company_name']}")
        print(f"🏫 School: {student_profile['school_12th']}")
        print(f"📧 Contact: {student_profile['email']}")
        print("="*70)
    else:
        print("⚠️ No student profile loaded - questions will be generic")
        print("="*70)

    # Check if command line arguments are provided or if running interactively
    if args.non_interactive or any([args.essay_topic, args.college, args.degree, args.major, args.word_limit]):
        # Use command line arguments or defaults
        print("📋 Using command line arguments/defaults")
        essay_topic = args.essay_topic or "Why do you want to pursue an MBA and how will it help achieve your career goals?"
        college_name = args.college or "Harvard Business School"
        degree = args.degree or "MBA"
        major = args.major or "Business Administration"
        word_limit = args.word_limit or "500"
    else:
        # Try interactive input
        try:
            # Try to get input interactively
            essay_topic = input("✏️ Enter essay topic/prompt: ").strip()
            if not essay_topic:
                essay_topic = "Personal statement"

            college_name = input("🏫 Enter college name: ").strip()
            if not college_name:
                college_name = "your target college"

            degree = input("🎓 Enter degree (e.g., UG, MBA, MS): ").strip()
            if not degree:
                degree = "undergraduate"

            major = input("📚 Enter major/field of interest: ").strip()
            if not major:
                major = "your chosen field"

            word_limit = input("📏 Enter word limit (e.g., 250, 500, 1000): ").strip()
            if not word_limit or not word_limit.isdigit():
                word_limit = "500"  # Default to 500 words if not specified
        
        except EOFError:
            # Use default values when input is not available
            print("📋 Using default values (non-interactive mode)")
            essay_topic = "Why do you want to pursue an MBA and how will it help achieve your career goals?"
            college_name = "Harvard Business School"
            degree = "MBA"
            major = "Business Administration"
            word_limit = "500"

    # Store user data
    user_data = {
        'essay_topic': essay_topic,
        'college_name': college_name,
        'degree': degree,
        'major': major,
        'word_limit': word_limit
    }

    # Print user inputs for confirmation
    print("\n" + "="*60)
    print("📋 YOUR INPUTS:")
    print("="*60)
    print(f"✏️  Essay Topic/Prompt: {essay_topic}")
    print(f"🏫 College Name: {college_name}")
    print(f"🎓 Degree: {degree}")
    print(f"📚 Major/Field: {major}")
    print(f"📏 Word Limit: {word_limit} words")
    print("="*60)

    # Interactive Q&A session
    conversation_history = []
    total_input_tokens = 0
    total_output_tokens = 0
    max_questions = 5

    print(f"\n🚀 Starting interactive brainstorming session!")
    print(f"I'll ask you questions one by one, and each question will build on your previous answers.")
    print(f"Stay focused on: '{essay_topic}'\n")

    for question_num in range(1, max_questions + 1):
        print(f"\n" + "="*50)
        print(f"QUESTION {question_num} of {max_questions}")
        print("="*50)
        
        # Generate question based on conversation history
        print("🤔 Generating your next question...")
        question, input_tokens, output_tokens = generate_single_question(
            essay_topic, college_name, major, word_limit, 
            question_num, conversation_history
        )
        
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        
        print(f"\n❓ {question}")
        print("\n💭 Your answer:")
        
        try:
            user_answer = input("➤ ").strip()
            
            if not user_answer:
                print("⚠️ No answer provided. Moving to next question...")
                user_answer = "[No answer provided]"
        except EOFError:
            # Generate dynamic default answers based on student profile
            default_answers = [
                f"I became interested in this field during my work at {student_profile.get('company_name', 'my workplace')} where I saw opportunities for improvement and innovation.",
                f"A specific challenge was navigating complex processes in {student_profile.get('work_experience', 'my professional environment')}, which required developing new skills and approaches.",
                f"This experience taught me the importance of balancing theoretical knowledge with practical implementation.",
                f"I realized I need stronger analytical and strategic thinking skills to successfully drive meaningful change in my field.",
                f"In five years, I want to have successfully implemented my vision and applied these learnings to create broader positive impact."
            ]
            user_answer = default_answers[min(question_num - 1, len(default_answers) - 1)]
            print(f"➤ {user_answer}")
            print("📋 (Using dynamic default answer based on profile)")
        
        # Store question-answer pair
        conversation_history.append({
            'question': question,
            'answer': user_answer
        })
        
        print(f"✅ Answer recorded! ({len(user_answer)} characters)")
        
        # Ask if user wants to continue
        if question_num < max_questions:
            print(f"\n🔄 Ready for question {question_num + 1}?")
            try:
                continue_choice = input("Press Enter to continue, or 'q' to finish early: ").strip().lower()
                if continue_choice == 'q':
                    print("⏹️ Session ended early by user.")
                    break
            except EOFError:
                # In non-interactive mode, continue automatically
                print("📋 Continuing automatically (non-interactive mode)")
                continue
    
    # Session summary
    print("\n" + "="*60)
    print("📊 SESSION SUMMARY")
    print("="*60)
    print(f"✅ Questions Asked: {len(conversation_history)}")
    print(f"📝 Essay Topic: {essay_topic}")
    print(f"🏫 College: {college_name}")
    print(f"📏 Word Limit: {word_limit} words")
    
    print("\n💭 YOUR RESPONSES RECAP:")
    for i, qa in enumerate(conversation_history, 1):
        print(f"\nQ{i}: {qa['question']}")
        print(f"A{i}: {qa['answer'][:100]}{'...' if len(qa['answer']) > 100 else ''}")
    
    print("\n" + "="*60)
    print("💡 NEXT STEPS:")
    print("Use these questions and your answers to craft your essay!")
    print("Focus on the most compelling stories and insights from your responses.")
    if int(word_limit) <= 500:
        print("📝 For shorter essays, pick 1-2 key themes from your answers.")
    elif int(word_limit) <= 1000:
        print("📝 For medium essays, you can develop 2-3 themes with examples.")
    else:
        print("📝 For longer essays, use multiple stories and deeper reflection.")
    print("="*60)

    # Save everything to CSV
    save_qa_to_csv(user_data, conversation_history, total_input_tokens, total_output_tokens)
    
    print(f"\n💾 All data has been saved to op.csv with timestamp!")

def run_interactive_conversation_with_csv(student_csv_path):
    """Run the interactive conversation system with a specific student CSV file"""
    
    global STUDENT_CSV_PATH, student_profile
    STUDENT_CSV_PATH = student_csv_path
    
    print(f"📄 Using student data from: {student_csv_path}")
    student_profile = load_student_profile_from_csv(student_csv_path)
    
    print("🚀 Starting Interactive RAG Essay Q&A System")
    print("=" * 50)
    
    # Start the interactive conversation
    main()
    
    print("\n" + "=" * 50)
    print("✅ Session completed! Check your saved files:")
    print("   📄 Latest conversation: latest_conversation.json")
    print("   📊 Full output: op.csv")
    print("\n🎯 Next step: Use this data with your structure generation system!")
    print("\n💡 Tip: The latest_conversation.json is ready to use with structure_rag.py")

if __name__ == "__main__":
    if STUDENT_CSV_PATH:
        print("🚀 Starting Interactive RAG Essay Q&A System")
        print("=" * 50)
        main()
    else:
        print("❌ Please specify your student CSV file path in the configuration section!")
        print("\n📝 USAGE INSTRUCTIONS:")
        print("=" * 60)
        print("METHOD 1 - Edit the configuration at the top of this file:")
        print("   Line 20: STUDENT_CSV_PATH = '/path/to/your/student_data.csv'")
        print("\nMETHOD 2 - Call the function directly:")
        print("   from RAG import run_interactive_conversation_with_csv")
        print("   run_interactive_conversation_with_csv('/path/to/your/file.csv')")
        print("\n💡 Example CSV path:")
        print("   STUDENT_CSV_PATH = '/Users/yourname/Documents/student_data.csv'")
        print("\n🔧 Your CSV should contain columns like:")
        print("   - Name, Email, GPA, Degree, Company, Leadership, Work_Experience")
        print("   - Any column names work - the system maps them automatically!")
        print("\n📋 Sample CSV format:")
        print("   Name,College,Major,GPA,Company,Leadership")
        print("   John Doe,NYU,Policy,93%,Transport Co,Enactus Leader")