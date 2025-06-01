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
import uuid
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

# Track Active Interview Sessions
active_sessions = {}

# Creating a TEMP directory in project root
TEMP_DIR = os.path.join(os.getcwd(), 'temp_audio')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


def speak_question(question):
    """Helper function to speak a question using TTS"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 160)
        voices = engine.getProperty('voices')
        if len(voices) > 1:
            engine.setProperty('voice', voices[1].id)
        engine.say(question)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"Error with Text to Speech: {e}")
        return str(e)
    return None


def run_interview(session_id, description, resume_data, num_questions=5):
    """Background thread to run interview process with dynamic inputs"""
    global active_sessions

    try:
        print(f"Starting interview session: {session_id}")

        # Step 1: Save description to temporary file
        des_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
        des_file.write(description)
        des_path = des_file.name
        des_file.close()
        print("Saved description file successfully!")

        # Step 2: Save resume to temporary file
        res_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json')
        json.dump(resume_data, res_file)
        res_path = res_file.name
        res_file.close()
        print("Saved resume file successfully!")

        # Initialize LLM
        llm = Ollama(model="llama3")

        # Initialize the session
        session = {
            "active": True,
            "questions": [],
            "current_index": 0,
            "interview_data": {},
            "analysis": "",
            "completed": False,
            "generate_followup": True,
            "updated_portfolio": {},
            "waiting_for_answer": False,
            "answer_received": threading.Event()
        }
        active_sessions[session_id] = session

        # Step 3: Generate initial questions
        print("Generating questions using LLM...")
        socketio.emit('interview_status', {'status': 'generating_questions'}, room=session_id)

        questions = generate_custom_questions(
            number_of_questions=num_questions,
            description=description,
            candidate_resume=resume_data,
            llm_model=llm
        )

        session["questions"] = questions
        print(f"Generated {len(questions)} questions")

        # Step 4: Process questions one by one
        question_index = 0
        while question_index < len(session["questions"]) and session["active"]:
            current_question = session["questions"][question_index]
            session["current_index"] = question_index
            session["waiting_for_answer"] = True
            session["answer_received"].clear()

            print(f"Asking question {question_index + 1}: {current_question}")

            # Emit the question to frontend
            socketio.emit('new_question', {
                'question': current_question,
                'question_number': question_index + 1,
                'total_questions': len(session["questions"])
            }, room=session_id)

            # Speak the question
            tts_error = speak_question(current_question)
            if tts_error:
                socketio.emit('tts_error', {'error': tts_error}, room=session_id)

            # Wait for answer with timeout
            print(f"Waiting for answer to question {question_index + 1}...")
            answer_received = session["answer_received"].wait(timeout=300)  # 5 minutes timeout

            if not answer_received:
                print(f"Timeout waiting for answer to question {question_index + 1}")
                socketio.emit('interview_error', {
                    'error': f'Timeout waiting for answer to question {question_index + 1}'
                }, room=session_id)
                break

            if not session["active"]:
                print("Session was cancelled")
                break

            session["waiting_for_answer"] = False
            print(f"Received answer for question {question_index + 1}")

            # Generate follow-up question if enabled and not the last question
            if (session.get("generate_followup", False) and
                    question_index < num_questions - 1 and  # Only for original questions, not follow-ups
                    current_question in session["interview_data"]):

                try:
                    print("Generating follow-up question...")
                    answer = session["interview_data"][current_question]
                    follow_up = generate_follow_up(
                        question=current_question,
                        answer=answer,
                        model=llm
                    )
                    # Insert follow-up after current question
                    session["questions"].insert(question_index + 1, follow_up)
                    print(f"Follow-up added. Total questions now: {len(session['questions'])}")
                except Exception as e:
                    print(f"Error generating follow-up: {e}")

            question_index += 1

        # Step 5: Analyze if interview completed successfully
        if session["active"] and len(session["interview_data"]) > 0:
            print("Starting analysis...")
            socketio.emit('interview_status', {'status': 'analyzing_responses'}, room=session_id)

            try:
                strengths_weaknesses_analysis = analyze_strengths_and_weaknesses(
                    interview_data=session["interview_data"],
                    llm_model=llm
                )

                session["analysis"] = strengths_weaknesses_analysis
                session["completed"] = True

                # Update portfolio
                updated_portfolio = resume_data.copy()
                if "strengths_weaknesses" not in updated_portfolio:
                    updated_portfolio["strengths_weaknesses"] = {}

                updated_portfolio["strengths_weaknesses"] = strengths_weaknesses_analysis
                session["updated_portfolio"] = updated_portfolio

                # Send completion notification
                socketio.emit('interview_complete', {
                    'analysis': strengths_weaknesses_analysis,
                    'updated_portfolio': updated_portfolio
                }, room=session_id)

                print("Interview analysis completed successfully")

            except Exception as e:
                print(f"Error in analysis: {e}")
                socketio.emit('interview_error', {'error': f'Analysis failed: {str(e)}'}, room=session_id)

        # Cleanup temporary files
        try:
            os.unlink(des_path)
            os.unlink(res_path)
            print("Temporary files cleaned up")
        except:
            pass

    except Exception as err:
        print(f"Error in interview session: {err}")
        socketio.emit('interview_error', {'error': str(err)}, room=session_id)

    finally:
        # Session cleanup
        if session_id in active_sessions:
            active_sessions[session_id]["active"] = False
        print(f"Interview session {session_id} ended")


@app.route('/api/')
def app_client():
    return render_template('interview_frontend.html')


@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    # Generate a unique session ID
    session_id = f"session_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    # Extract form data
    embassy = request.form.get("embassy_or_consulate", "").strip()
    destination_country = request.form.get("destination_country", "").strip()
    course = request.form.get("course", "").strip()
    university = request.form.get("university", "").strip()

    # Validate required fields
    if not all([embassy, destination_country, course, university]):
        return jsonify({
            "mtype": "error",
            "message": "All fields (embassy, destination country, course, university) are required"
        }), 400

    # Generate dynamic prompt
    filled_prompt = visa_interview_prompt.format(
        embassy_or_consulate=embassy,
        destination_country=destination_country,
        course=course,
        university=university
    )

    # Process resume file
    resume_data = {}
    if 'resume_file' in request.files:
        resume_file = request.files['resume_file']
        if resume_file.filename != '' and resume_file.filename.endswith('.json'):
            try:
                resume_data = json.loads(resume_file.read().decode('utf-8'))
                print("Resume data loaded successfully")
            except json.JSONDecodeError as e:
                return jsonify({
                    "mtype": "error",
                    "message": f"Invalid JSON format in resume file: {str(e)}"
                }), 400
        else:
            return jsonify({
                "mtype": "error",
                "message": "Resume file must be in JSON format"
            }), 400
    else:
        return jsonify({
            "mtype": "error",
            "message": "Resume file is required"
        }), 400

    # Get number of questions
    try:
        num_questions = int(request.form.get("num_questions", "3"))
        if num_questions < 1 or num_questions > 10:
            num_questions = 3
    except ValueError:
        num_questions = 3

    print(f"Starting interview session {session_id} with {num_questions} questions")

    # Start interview in background thread
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
    print(f"Client connected: {request.sid}")


@socketio.on('join_session')
def handle_join(data):
    session_id = data.get('session_id')
    if not session_id:
        emit('error', {'message': 'No session ID provided'})
        return

    from flask_socketio import join_room
    join_room(session_id)
    emit('joined_session', {'session_id': session_id})
    print(f"Client joined session: {session_id}")


@socketio.on('submit_answer')
def handle_answer(data):
    session_id = data.get('session_id')
    if not session_id or session_id not in active_sessions:
        emit('error', {'message': 'Invalid session ID'})
        return

    session = active_sessions[session_id]
    if not session["active"]:
        emit('error', {'message': 'Session is not active'})
        return

    if not session["waiting_for_answer"]:
        emit('error', {'message': 'Not waiting for an answer'})
        return

    if session["current_index"] >= len(session["questions"]):
        emit('error', {'message': 'No active question'})
        return

    current_question = session["questions"][session["current_index"]]
    answer_text = data.get('text', '').strip()
    audio_data = data.get('audio')
    answer = ""

    print(f"Processing answer for question {session['current_index'] + 1}")

    # Process audio if provided
    if audio_data:
        temp_audio_path = None
        try:
            # Decode and save audio
            audio_bytes = base64.b64decode(audio_data)
            temp_filename = f"temp_audio_{uuid.uuid4().hex}.wav"
            temp_audio_path = os.path.join(TEMP_DIR, temp_filename)

            with open(temp_audio_path, 'wb') as temp_file:
                temp_file.write(audio_bytes)

            print(f"Audio saved to: {temp_audio_path}")

            # Verify file
            if not os.path.exists(temp_audio_path) or os.path.getsize(temp_audio_path) == 0:
                raise ValueError("Audio file is empty or not created")

            # Transcribe with Whisper
            print("Starting transcription...")
            model = whisper.load_model("base")
            result = model.transcribe(temp_audio_path, fp16=False)
            answer = result["text"].strip()

            print(f"Transcription successful: {answer}")
            emit('transcription_result', {'transcription': answer})

        except Exception as e:
            print(f"Error processing audio: {e}")
            emit('transcription_error', {'error': str(e)})
            answer = answer_text or "Unable to process audio response"

        finally:
            # Cleanup temp file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                    print("Temporary audio file cleaned up")
                except Exception as cleanup_error:
                    print(f"Cleanup error: {cleanup_error}")
    else:
        # Use text answer
        answer = answer_text

    if not answer:
        emit('error', {'message': 'No answer provided'})
        return

    # Store the answer
    session["interview_data"][current_question] = answer
    session["generate_followup"] = data.get("generateFollowUp", True)

    print(f"Answer stored for question {session['current_index'] + 1}: {answer[:100]}...")

    # Signal that answer was received
    session["answer_received"].set()

    # Send confirmation to client
    emit('answer_received', {
        'question': current_question,
        'answer': answer,
        'transcription': answer if audio_data else None,
        'mtype': 'success',
        'qlength': len(session['questions']),
        'current_question_number': session['current_index'] + 1
    })


@socketio.on('cancel_interview')
def handle_cancel(data):
    session_id = data.get('session_id')
    if session_id and session_id in active_sessions:
        active_sessions[session_id]["active"] = False
        active_sessions[session_id]["answer_received"].set()  # Unblock waiting thread
        emit('interview_cancelled', {}, room=session_id)
        print(f"Interview session {session_id} cancelled")


@app.route('/api/get-analysis', methods=['GET'])
def get_analysis():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in active_sessions:
        return jsonify({
            "mtype": "error",
            "message": "Invalid Session ID"
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
    socketio.run(app=app, debug=True, host='0.0.0.0', port=5000)