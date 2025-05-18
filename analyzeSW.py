def analyze_strengths_and_weaknesses(interview_data, llm_model):
    

        # Define prompts based on the question and expected responses
        prompt = f"Identify strengths and weaknesses in the candidate's interview based on the confidence and detailness of the answers, Give me strengths and weaknesses ,Strictly based on this format. Strengths: , Weaknesses:  ,Here is the interview dictionary with questions and its answers {interview_data}\n"

        # Use Llama3 to generate responses based on prompts
        response = llm_model.invoke(prompt)

        # Analyze Llama3 generated responses to determine strengths and weaknesses
        print("Updated Strengths and Weaknesses!")
        return response
        