import whisper
import time
import pyttsx3
from extract_SW import add_strengths_and_weaknesses_to_portfolio
from question_gen import generate_custom_questions
from read_file_json import read_file, read_json
from audio_conversion import speech_to_text
from analyzeSW import analyze_strengths_and_weaknesses
from follow_up_gen import generate_follow_up
from langchain_ollama import OllamaLLM

# Initialize interview data dictionary
interview_data = {}


def store_interview(question, answer):
    """Store question and answer in interview_data dictionary."""
    global interview_data
    interview_data[question] = answer


engine = pyttsx3.init()
engine.setProperty('rate', 160)
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)


def interview_module():
    "Main function to conduct the interview process."
    llm = OllamaLLM(model="llama3")
    whisper_model = whisper.load_model("base")

    job_description = read_file('jd.txt')

    candidate_resume = read_json('portfolio.json')
    # these are the main parameters for the complete module, change the number of questions here, later these will
    # be passed from a flask endpoint
    questions_list = generate_custom_questions(2, job_description, candidate_resume, llm)

    for question in questions_list:

        print(f"{question}")
        engine.say(question)
        engine.runAndWait()
        time.sleep(8)
        answer = None
        while not answer:  # Keep listening until valid answer is received
            answer = speech_to_text(whisper_model)
        store_interview(question, answer)

        # Generate follow-up question and retrieve answer
        follow_up_question = generate_follow_up(question, answer, llm)
        time.sleep(8)

        # Ask for follow-up answer
        follow_up_answer = None
        while not follow_up_answer:  # Keep listening until valid follow-up answer is received
            follow_up_answer = speech_to_text(whisper_model)

        store_interview(follow_up_question, follow_up_answer)

        # Generate and retrieve the next follow-up question
        # follow_up_question = generate_follow_up(follow_up_question, follow_up_answer, llm)
        # time.sleep(8)

        # # Ask for follow-up answer
        # follow_up_answer = None
        # while not follow_up_answer:  # Keep listening until valid follow-up answer is received
        #     follow_up_answer = speech_to_text(whisper_model)

        # store_interview(follow_up_question, follow_up_answer)
        print("Moving on...\n")

        # After all questions are answered, analyze strengths and weaknesses
    strengths_weaknesses_analysis = analyze_strengths_and_weaknesses(interview_data, llm)
    portfolio_file = 'portfolio.json'
    add_strengths_and_weaknesses_to_portfolio(portfolio_file, strengths_weaknesses_analysis)


if __name__ == "__main__":
    interview_module()
