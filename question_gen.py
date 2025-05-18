import re

def generate_custom_questions(number_of_questions, description, candidate_resume, llm_model):
    """Generate custom questions based on job description and candidate resume."""
    if number_of_questions and description and candidate_resume and llm_model is not None:
        print(f"Generating {number_of_questions} Questions using {llm_model}")
        prompt = (
            f"Only Generate {number_of_questions} interview questions based on the following visa description requirements and the candidate description. Check if the candidate is the right fit for the visa processing considering their response. strictly follow the format of just giving questions.\n"
            f"Job Description: {description}\n"
            f"Candidate Resume: {candidate_resume}\n"
        )
        try:
            questions = llm_model.invoke(prompt)
            question_list = re.findall(r'\d+\.\s.*', questions)

            # Strip leading/trailing whitespace from each question
            question_list = [q.strip() for q in question_list]
            print(f"Generated {len(question_list)} Questions")
            return question_list
        except Exception as err:
            print(f"Error Generating Questions: {err}")
            return err
    else:
        print("Incomplete Parameters Please include all fields")
