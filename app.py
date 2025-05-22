import os
import threading
import base64
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import whisper
from langchain_community.llms import Ollama
import json
import tempfile
import time
import pyttsx3
from extract_SW import add_strengths_and_weaknesses_to_portfolio
from question_gen import generate_custom_questions
from read_file_json import read_file, read_json
from audio_conversion import speech_to_text
from analyzeSW import analyze_strengths_and_weaknesses
from follow_up_gen import generate_follow_up
from description import visa_interview_prompt


# Initial Config
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Shared State Between Routes
interview_state = {
    "active": False,
    "questions": [],
    "current_index": 0,
    "interview_data": {},
    "analysis": "",
    "completed": False,
    "updated_portfolio": None
}

# Track Active Interview Sessions
active_sessions = {}


def run_interview(session_id, description, resume_data, num_questions=5):
    """Background thread to run interview process with dynamic inputs"""
    global active_sessions

    try:
        print("Starting the interview session")

        print("Step 1 Save the description to a temporary file")
        des_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
        des_file.write(description)
        des_path = des_file.name
        des_file.close()
        print("Saved the description file successfully!")

        print("Step 2 Save the Resume to a temporary file")
        res_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json')
        json.dump(resume_data, res_file)
        res_path = res_file.name
        res_file.close()
        print("Saved the resume file successfully!")

        # Initialize LLM
        llm = Ollama(model="llama3")

        # Load whisper
        whisper_model = whisper.load_model("base")

        # Initialize the session
        session = {
            "active": True,
            "questions": [],
            "current_index": 0,
            "interview_data": {},
            "analysis": "",
            "completed": False,
            "generate_followup": True,
            "updated_portfolio": {}
        }
        active_sessions[session_id] = session

        # Generate questions using description and resume
        print("Step 3 Generate Questions using the LLM")
        socketio.emit('interview_status', {'status': 'generating_questions'}, room=session_id)
        questions = generate_custom_questions(
            number_of_questions=num_questions,
            description=description,
            candidate_resume=resume_data,
            llm_model=llm
        )

        print("Step 4 Store the generated questions in the session")
        print(f"Number of questions generated: {len(questions)}")
        session["questions"] = questions

        # Now we process each question sequentially
        for idx, question in enumerate(questions):
            session["current_index"] = idx
            socketio.emit('new_question', {
                'question': question,
                'question_number': idx + 1,
                'total_questions': len(questions)
            }, room=session_id)
            # Speak this question
            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', 160)
                voices = engine.getProperty('voices')
                engine.setProperty('voice', voices[1].id)
                engine.say(question)
                engine.runAndWait()
            except Exception as e3:
                print(f"Error with Test to Speech: {e3}")
                socketio.emit('tts_error', {'error': str(e3)}, room=session_id)
            # Wait for the answer from the client side
            # Actual Handling in Web Sock Events
            while session["current_index"] == idx and session["active"]:
                time.sleep(0.5)
            if not session["active"]:
                break

            # After answer is received a follow-up question should be generated
            if idx < len(questions) - 1 and "generate_followup" in session and session["generate_followup"]:
                current_question = session["questions"][idx]
                answer = session["interview_data"].get(current_question, "")

                try:
                    follow_up = generate_follow_up(question=current_question, answer=answer, model=llm)
                    session["questions"].insert(idx + 1, follow_up)
                    questions = session["questions"]
                except Exception as e4:
                    print(f"Error Generating Follow-up Question: {e4}")

        # After all the questions are answered, Analyze the Strengths and Weaknesses
        print("Step 5 S&W Analysis")
        try:
            socketio.emit('interview_status', {'status': 'analyzing_responses'}, room=session_id)
            strengths_weaknesses_analysis = analyze_strengths_and_weaknesses(
                interview_data=session["interview_data"],
                llm_model=llm
            )
            session["analysis"] = strengths_weaknesses_analysis
            session["completed"] = True
            # Update the portfolio with S&W
            updated_portfolio = resume_data.copy()

            if "strengths_weaknesses" not in updated_portfolio:
                updated_portfolio["strengths_weaknesses"] = {}
                updated_portfolio["strengths_weaknesses"] = strengths_weaknesses_analysis
                session["updated_portfolio"] = updated_portfolio
                # Send Completion Notification
                socketio.emit('interview_complete', {
                    'analysis': strengths_weaknesses_analysis,
                    'updated_portfolio': updated_portfolio
                }, room=session_id)
            # Clean Up Temporary Files
            try:
                os.unlink(des_path)
                os.unlink(res_path)
            except:
                pass

        except Exception as e5:
            print(f"Error in performing S&W Analysis: {e5}")

    except Exception as err:
        print(f"An error occurred in running the interview session: {err}")
        socketio.emit('interview_error', {'error': str(err)}, room=session_id)

        # Session Clean Up
        if session_id in active_sessions:
            active_sessions[session_id]["active"] = False


@app.route('/api/')
def app_client():
    return render_template('interview_frontend.html')


@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    # Generate a Session ID
    session_id = request.sid if hasattr(request, 'sid') else f"session_{int(time.time())}"

    # Generate the dynamic prompt
    embassy = request.form.get("embassy_or_consulate", ""),
    destination_country = request.form.get("destination_country", ""),
    course = request.form.get("course", ""),
    university = request.form.get("university", "")

    filled_prompt = visa_interview_prompt.format(
        embassy_or_consulate=embassy,
        destination_country=destination_country,
        course=course,
        university=university)

    resume_data = {}
    if 'resume_file' in request.files:
        resume_file = request.files['resume_file']
        if resume_file.filename != '' and resume_file.filename.endswith('.json'):
            try:
                print("Loading Resume Data")
                resume_data = json.loads(resume_file.read().decode('utf-8'))
            except json.JSONDecodeError:
                return jsonify({
                    "mtype": "error",
                    "message": "Invalid JSON format, error parsing the file"
                }), 400
    try:
        print("Extracting Number of Questions from Form Data")
        num_questions = int(request.form.get("num_questions", "2"))
    except ValueError:
        num_questions = 2

    # Input Field Validation Logic
    if not embassy or not destination_country or not course or not university:
        return jsonify({
            "mtype": "warning",
            "message": "Compulsory Fields are Required"
        }), 400

    if not resume_data:
        return jsonify({
            "mtype": "warning",
            "message": "Resume Data File is required"
        }), 400

    # Start the Interview Process in the Background
    thread = threading.Thread(
        target=run_interview,
        args=(session_id, filled_prompt, resume_data, num_questions)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        "mtype": "success",
        "message": "Interview started successfully",
        "session_id": session_id
    })


@socketio.on('connect')
def handle_connect():
    print(f"Client Connected: {request.sid}")


@socketio.on('join_session')
def handle_join(data):
    session_id = data.get('session_id')
    if not session_id:
        emit('error', {'message': 'No session ID provided'})
        return

    # Join the room corresponding to this session
    from flask_socketio import join_room
    join_room(session_id)
    emit('joined_session', {'session_id': session_id})


@socketio.on('submit_answer')
def handle_answer(data):
    session_id = data.get('session_id')
    if not session_id or session_id not in active_sessions:
        emit('error', {'message': 'Invalid session ID'})
        return

    session = active_sessions[session_id]
    if not session["active"] or session["current_index"] >= len(session["questions"]):
        emit('error', {'message': 'No active question'})
        return

    current_question = session["questions"][session["current_index"]]
    answer_text = data.get('text')
    audio_data = data.get('audio')  # Base64 encoded audio if available

    # Process the answer based on what was provided
    if audio_data:
        # If audio was provided, convert it to text
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio_file:
                temp_audio_path = temp_audio_file.name
                temp_audio_file.write(audio_bytes)

            # Use whisper to transcribe
            model = whisper.load_model("base")
            result = model.transcribe(temp_audio_path)
            answer = result["text"]

            # Clean up temp file
            os.unlink(temp_audio_path)

        except Exception as e:
            print(f"Error processing audio: {e}")
            emit('transcription_error', {'error': str(e)})
            # Fall back to text answer if provided
            answer = answer_text or "Unable to process audio response"
    else:
        # Use provided text answer
        answer = answer_text or "No answer provided"

    # Store in interview data
    session["interview_data"][current_question] = answer

    # Save whether to generate a follow-up
    session["generate_followup"] = data.get("generateFollowUp", True)

    # Move to next question (the main thread will handle the follow-up)
    session["current_index"] += 1

    emit('answer_received', {
        'question': current_question,
        'answer': answer,
        'transcription': answer if audio_data else None
    })


@socketio.on('cancel_interview')
def handle_cancel(data):
    session_id = data.get('session_id')
    if session_id and session_id in active_sessions:
        active_sessions[session_id]["active"] = False
        emit('interview_cancelled', {}, room=session_id)

@app.route('/api/get-analysis', methods=['GET'])
def get_analysis():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({
            "mtype": "warning",
            "message": "Invalid Session ID",
        }), 400

    session = active_sessions[session_id]

    if not session["completed"]:
        return jsonify({
            "mtype": "warning",
            "message": "Analysis not yet complete"
        })

    return jsonify({
        "mtype": "success",
        "analysis": session["analysis"],
        "updated_portfolio": session["updated_portfolio"]
    })

if __name__ == '__main__':
    socketio.run(app=app, debug=True)