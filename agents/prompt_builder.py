from typing import Dict, Any, Optional
from backend.data_services.mongo.user_repository import UserRepository
from backend.data_services.mongo.assistant_repository import get_assistant_by_id

user_repository = UserRepository()

async def build_personalized_prompt(user_id: str, assistant_id: str = None) -> str:
    """
    Build a personalized system prompt incorporating user information and assistant configuration.
    
    Args:
        user_id: The user's ID
        assistant_id: Optional assistant ID for specific assistant configuration
    
    Returns:
        str: Personalized system prompt
    """
    try:
        # Get user information
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get assistant configuration if provided
        assistant_config = None
        if assistant_id:
            assistant_config = get_assistant_by_id(assistant_id)
            if not assistant_config:
                raise ValueError(f"Assistant {assistant_id} not found")
        
        # Extract user information from the structured resume
        resume = user.get('resume', {})
        user_info = {
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "summary": resume.get('summary', ''),
            "skills": resume.get('skills', []),
            "work_experience": resume.get('work_experience', []),
            "education": resume.get('education', []),
            "languages": resume.get('languages', []),
            "links": resume.get('links', []),
            "phone": resume.get('phone', ''),
            "job_title": user.get('job_title', 'Unknown'),
            "organization_id": user.get('organization_id', 'Unknown')
        }
        
        # Build the personalized prompt
        prompt = f"""User Context:
Name: {user_info['name']}
Role: {user_info['job_title']}
Organization: {user_info['organization_id']}

{f"""You are a personal AI assistant for {user_info['name']}. You have deep knowledge about them and their background.

PERSONAL INFORMATION:
- Name: {user_info['name']}
- Contact: {user_info['phone']}
- Professional Links: {', '.join(user_info['links'])}

PROFESSIONAL SUMMARY:
{user_info['summary']}

WORK EXPERIENCE:
{format_work_experience(user_info['work_experience'])}

EDUCATION:
{format_education(user_info['education'])}

SKILLS:
{', '.join(user_info['skills'])}

LANGUAGES:
{', '.join(user_info['languages'])}

YOUR ROLE:
1. You are their personal assistant, deeply familiar with their background and needs
2. Use their professional context to provide more relevant and personalized responses
3. Maintain a professional yet friendly tone
4. Be proactive in suggesting relevant actions based on their background
5. Respect their privacy and professional boundaries
6. When unsure, ask for clarification rather than making assumptions

RESPONSE GUIDELINES:
1. Be concise but thorough
2. Use their professional context to provide more relevant suggestions
3. Maintain a balance between professional and friendly communication
4. Consider their technical background when explaining concepts
5. Be proactive in offering relevant assistance based on their profile

IMPORTANT:
- Always maintain professional confidentiality
- Never share sensitive personal information
- Confirm before taking actions on their behalf
- Consider their technical expertise when providing information
- Use their professional context to provide more relevant assistance"""}"""

        # Add assistant-specific configuration if provided
        if assistant_config:
            prompt += f"""

ASSISTANT CONFIGURATION:
- Name: {assistant_config.get('name', 'AI Assistant')}
- Type: {assistant_config.get('type', 'General')}
- Responsibilities: {', '.join(assistant_config.get('responsibilities', ['General assistance']))}
- Additional Instructions: {assistant_config.get('instructions', '')}"""

        return prompt
    except Exception as e:
        print(f"Error building personalized prompt: {str(e)}")
        return f"""You are a personal AI assistant for {user_info['name']}. You have deep knowledge about them and their background.

PERSONAL INFORMATION:
- Name: {user_info['name']}
- Contact: {user_info['phone']}
- Professional Links: {', '.join(user_info['links'])}

PROFESSIONAL SUMMARY:
{user_info['summary']}

WORK EXPERIENCE:
{format_work_experience(user_info['work_experience'])}

EDUCATION:
{format_education(user_info['education'])}

SKILLS:
{', '.join(user_info['skills'])}

LANGUAGES:
{', '.join(user_info['languages'])}

YOUR ROLE:
1. You are their personal assistant, deeply familiar with their background and needs
2. Use their professional context to provide more relevant and personalized responses
3. Maintain a professional yet friendly tone
4. Be proactive in suggesting relevant actions based on their background
5. Respect their privacy and professional boundaries
6. When unsure, ask for clarification rather than making assumptions

RESPONSE GUIDELINES:
1. Be concise but thorough
2. Use their professional context to provide more relevant suggestions
3. Maintain a balance between professional and friendly communication
4. Consider their technical background when explaining concepts
5. Be proactive in offering relevant assistance based on their profile

IMPORTANT:
- Always maintain professional confidentiality
- Never share sensitive personal information
- Confirm before taking actions on their behalf
- Consider their technical expertise when providing information
- Use their professional context to provide more relevant assistance"""

def format_work_experience(work_experience: list) -> str:
    """Format work experience information."""
    if not work_experience:
        return "No work experience information available"
    
    formatted = []
    for exp in work_experience:
        company = exp.get('company', 'Unknown Company')
        title = exp.get('title', 'Unknown Position')
        start_date = exp.get('start_date', '')
        end_date = exp.get('end_date', 'Present')
        description = exp.get('description', '')
        
        formatted.append(f"- {title} at {company} ({start_date} - {end_date})")
        if description:
            formatted.append(f"  {description}")
        formatted.append("")
    
    return '\n'.join(formatted)

def format_education(education: list) -> str:
    """Format education information."""
    if not education:
        return "No education information available"
    
    formatted = []
    for edu in education:
        institution = edu.get('institution', 'Unknown Institution')
        degree = edu.get('degree', '')
        field = edu.get('field', '')
        start_date = edu.get('start_date', '')
        end_date = edu.get('end_date', '')
        
        formatted.append(f"- {degree} in {field} from {institution} ({start_date} - {end_date})")
    
    return '\n'.join(formatted) 