import pyttsx3

def generate_follow_up(question, answer, model):
    """Generate follow-up question and retrieve answer using Llama3."""
    prompt = (
        f"Act like an interviewer and ask questions based on the response to get to know more about it in detail and only ask questions,be professional and to the point if needed. Here is the question asked and the response given by me .Interviewer: {question}\n Student: {answer}\n"
        f"Now ask a single question based on the response to test whether the candidate is giving expected answers! If the answer is very different from the question asked, ask them to stay on point and get in detail."
    )

    try:
        follow_up = model.invoke(prompt)
        print(follow_up)

        # Create a new TTS engine instance for this specific call
        local_engine = None
        try:
            local_engine = pyttsx3.init()
            local_engine.setProperty('rate', 160)
            voices = local_engine.getProperty('voices')
            if len(voices) > 1:
                local_engine.setProperty('voice', voices[1].id)
            local_engine.say(follow_up)
            local_engine.runAndWait()
        except RuntimeError as e:
            if "run loop already started" in str(e):
                print("TTS engine busy, skipping follow-up speech")
            else:
                print(f"TTS error in follow-up: {e}")
        except Exception as tts_error:
            print(f"TTS error in follow-up: {tts_error}")
        finally:
            if local_engine:
                try:
                    local_engine.stop()
                    del local_engine
                except:
                    pass

        return follow_up

    except Exception as e:
        print(f"Error in generate_follow_up: {e}")
        return None