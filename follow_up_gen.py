import re

def generate_follow_up(question, answer, model):
    """Generate follow-up question using the fine-tuned model"""

    prompt = f"""As a visa officer conducting an interview, I asked: "{question}"

The applicant answered: "{answer}"

Based on this response, generate ONE specific follow-up question that would help clarify or dig deeper into their answer. The follow-up should be professional and relevant to visa assessment.

Follow-up question:"""

    try:
        response = model.generate(prompt, max_tokens=200, temperature=0.7)

        # Clean up the response
        follow_up = response.strip()

        # Remove any prefixes or numbering
        follow_up = re.sub(r'^(Follow-up question:|Question:|Answer:|Response:)', '', follow_up,
                           flags=re.IGNORECASE).strip()

        # Ensure it's a question
        if follow_up and not follow_up.endswith('?'):
            follow_up += '?'

        return follow_up if follow_up and len(follow_up) > 10 else None

    except Exception as e:
        print(f"Error generating follow-up: {e}")
        return None