import os
import sys
import django

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from utils.email import send_chatbot_report_email

def test_chatbot_report_email():
    test_email = "ayush@reachivy.com"  # Using user's domain for testing
    student_name = "Ayush"
    
    # Mock transcript (Paired structure)
    transcript = [
        {
            "bot_question": "Hello! I am your AI Coach. How are you today?",
            "student_response": "I am good, thanks! I want to explore career options in Engineering."
        },
        {
            "bot_question": "Great! Engineering is a vast field. Do you prefer Software or Civil?",
            "student_response": "I like Software and AI."
        },
        {
            "bot_question": "Excellent. Based on our chat, I recommend focusing on Computer Science and Data Science.",
            "student_response": ""
        },
    ]
    
    # Mock recommendations
    recommendations = [
        {
            "career_title": "Software Engineer",
            "match_percentage": 95,
            "description": "Building next-generation applications and systems."
        },
        {
            "career_title": "Data Scientist",
            "match_percentage": 88,
            "description": "Analyzing data to gain insights and make predictions."
        }
    ]
    
    print(f"Sending test chatbot report email to {test_email}...")
    try:
        send_chatbot_report_email(
            email=test_email,
            student_name=student_name,
            module_name="Career Discovery",
            transcript=transcript,
            recommendations=recommendations,
            session_id="test_session_123"
        )
        print("Success! Check the console output for the fallback preview if SendGrid is not configured.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_chatbot_report_email()
