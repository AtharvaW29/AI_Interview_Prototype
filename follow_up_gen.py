import pyttsx3

engine = pyttsx3.init()           
engine.setProperty('rate', 160)  
voices = engine.getProperty('voices') 
engine.setProperty('voice', voices[1].id)


def generate_follow_up(question, answer, model):
    """Generate follow-up question and retrieve answer using Llama3."""
    prompt = (
        f"Act like an interviewer and ask questions based on the response to get to know more about it in detail and only ask questions,be professional and to the point if needed. Here is the question asked and the response given by me .Interviewer: {question}\n Student: {answer}\n"
        f"Now ask a single question based on the response to test whether the candidate is giving expected answers! If the answer is very different from the question asked, ask them to stay on point and get in detail."
    )
    follow_up = model.invoke(prompt)
    print(follow_up)
    engine.say(follow_up)
    engine.runAndWait()
    return follow_up