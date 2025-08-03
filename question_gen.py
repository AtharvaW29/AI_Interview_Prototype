import re
import json

def generate_custom_questions(number_of_questions, description, candidate_resume, llm_model):
    """Generate custom questions using the fine-tuned model"""

    # Create a comprehensive prompt for question generation
    prompt = f"""As a visa officer, generate {number_of_questions} specific and relevant interview questions based on the following information:

Visa Application Context:
{description}

Candidate Resume/Background:
{json.dumps(candidate_resume, indent=2)}

Generate questions that:
1. Assess the candidate's genuine intent
2. Verify their qualifications and background
3. Test their knowledge about their stated purpose
4. Evaluate potential immigration risks
5. Are specific to their application details

Return only the questions, numbered 1-{number_of_questions}, one per line."""

    try:
        # Use the fine-tuned model's generate method
        response = llm_model.generate(prompt, max_tokens=800, temperature=0.7)

        # Parse the response to extract questions
        questions = []
        lines = response.strip().split('\n')

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # Remove numbering and clean up
                question = re.sub(r'^\d+[\.\)\-\s]+', '', line)
                question = re.sub(r'^[\-\*\s]+', '', question)
                if question.endswith('?') or len(question) > 20:
                    questions.append(question)

        # Ensure we have the requested number of questions
        if len(questions) < number_of_questions:
            # Add fallback questions if needed
            fallback_questions = [
                "Why do you want to visit the United States?",
                "How will you fund your stay in the US?",
                "What ties do you have to your home country?",
                "What are your plans after completing your studies/visit?",
                "Can you explain any gaps in your educational or employment history?"
            ]

            for fallback in fallback_questions:
                if len(questions) >= number_of_questions:
                    break
                if fallback not in questions:
                    questions.append(fallback)

        return questions[:number_of_questions]

    except Exception as e:
        print(f"Error generating questions: {e}")
        # Return default questions as fallback
        return [
                   "What is the purpose of your visit to the United States?",
                   "How long do you plan to stay in the US?",
                   "What are your educational qualifications?",
                   "How will you finance your studies/stay in the US?",
                   "What are your future career plans after your visit?"
               ][:number_of_questions]
