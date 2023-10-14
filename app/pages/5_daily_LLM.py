import streamlit as st
from datetime import datetime
import pickle
import openai
from langchain.llms import OpenAI
from langchain import PromptTemplate
import os
import sounddevice as sd
from scipy.io.wavfile import write
from gtts import gTTS
import openai
from collections import defaultdict
import json


def eval_res(question, user_response):
    prompt_ = """
            **ROLE:**
            You are LARA, an advanced digital assistant designed specifically to help people with dementia. 
            
            **TASK:**
            Determine whether the user's answer to the following question makes sense, return "OK" or "REPEAT" depending on whether you think the provided answer corresponds to the question.
        
            **Desired Output in a valid JSON Format:**
            {{"reason":<string explaining the decision>, "decision": ["OK", "REPEAT"]}}
            
            **Example 1:**
            Question: List down the activities you engaged in today
            User Response: Hello, my name is Jessica and I am doing well.
            Verdict: REPEAT
            Why you should decide like this: The response does not correspond to the question.

            **Example 2:**
            Question: List down the activities you engaged in today
            User Response: I cooked dinner.
            Verdict: OK
            Why you should decide like this: The response corresponds to the question.
            
            **Question:**
            {question}

            **User Response:**
            {user_response}

            This usecase is very important, let's make sure to get it right. 

            Please provide detailed reason explaining to the user in one or more sentences why they should answer the question again. Always structure the reason as if you were speaking to a person and provide enough detail and explanation.
            
            ###
            
            Output the answer in the desired JSON format:

            """
            
    template = PromptTemplate(template=prompt_, input_variables=["question" ,"user_response"])
    
    llm = OpenAI(model_name="gpt-4", temperature=0.5, max_tokens=300)
    prompt = template.format(question=question, user_response=user_response)
    res = llm(prompt)
    json_response = json.loads(res)
    print(f"RESPONSE LLM: {json_response}")
    
    return json_response['decision'], json_response['reason']

# Transcription function (reintegrating the original functionality)
def transcribe_audio(audio_file_name):
    # Actual transcription logic here
    # (You might need to integrate the OpenAI API or other transcription services)
    audio = open(audio_file_name, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio)
    return transcript

def record_audio(fs=44100, seconds=5, audio_file_name="input_audio_whisper.wav"):
    myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
    sd.wait()  # Wait until recording is finished
    write(audio_file_name, fs, myrecording)  # Save as WAV file

# Set the title of the app
st.title('Daily Diary')

# Check for the submission state
if 'daily_submitted' not in st.session_state:
    st.session_state.daily_submitted = False

if 'current_question' not in st.session_state:
    st.session_state.current_question = 1

if 'responses' not in st.session_state:
    st.session_state.responses = {}

# Automatically fetch the current date and time
current_datetime = datetime.now().strftime('%Y-%m-%d')

# Specify the file path where you want to save the pickle file
daily_file_path = f'data/daily_outputs_{current_datetime}.pickle'

def save_daily_outputs(daily_outputs):
    """Save data into json"""
    with open(daily_file_path, 'wb') as file:
        pickle.dump(daily_outputs, file)

def display_question(question, key, prefill_text=''):
    """Shows the next questions"""
    print(prefill_text)
    response = st.text_area(question, value=prefill_text)
    button_key = f"next_button_{st.session_state.current_question}"
    decision, reason = eval_res(question, response)
    if st.button('Next', key=button_key):
        if response and (decision=="OK"):
            st.session_state.responses[key] = response
            st.session_state.responses[key + "_check"] = True
            st.session_state.current_question += 1
            return response
        elif not response:
            st.warning('Please fill in the field before proceeding.')
            st.session_state.responses[key + "_check"] = False
        elif (decision=="REPEAT"):
            st.warning(f'Please answer the question again. {reason}')
            st.session_state.responses[key + "_check"] = False
        else:
            raise RuntimeError('FML')
        
        
            
def record_audio_and_transcribe(audio_name, key):
    audio_name = f"{audio_name}.wav"
    record_audio(audio_file_name=audio_name)
    user_input = transcribe_audio(audio_name)["text"]
    st.write(f'You Recorded: {user_input}')
    st.session_state.responses[key] = user_input

    if st.button('Continue'):
        st.session_state.current_question += 1
        return user_input
    
    
def display_daily_form():
    hidden_response_capture = defaultdict(str)
    for i in range(1, 10):
        hidden_response_capture[i] = ""
    
    
    # Mood and Emotions
    if st.session_state.current_question == 1:
        print("STATE IS 1")
        st.subheader('Mood and Emotions')
        st.write("Select your mood using emojis:")
        response = st.radio("", ['😄 Happy', '😊 Content', '😐 Neutral', '😞 Sad', '😢 Very Sad'], key='mood_radio')
        button_key = f"next_button_{st.session_state.current_question}"
        if st.button('Next', key=button_key):
            if response:
                st.session_state.responses['Day Mood'] = response
                st.session_state.current_question += 1
            else:
                st.warning('Please select a mood before proceeding.')

    # Activities
    elif st.session_state.current_question == 2:
        st.subheader('Activities')
        session_key = 'Day Activities'
        try:
            print(st.session_state.responses[session_key])
            pass
        except:
            st.session_state.responses[session_key] = None
            st.session_state.responses[session_key + "_check"] = False
        
        if not st.session_state.responses[session_key + "_check"]:    
            sb = st.button('Speak with LARA')
            if sb:
                _ = record_audio_and_transcribe("daily_activities", session_key)
            else:
                display_question('List down the activities you engaged in today.', session_key, st.session_state.responses[session_key])
        else:
            print("Not moving here anymore")


    # Daily Questions
    elif st.session_state.current_question == 3:
        st.subheader('Daily Questions')
        session_key = 'Day Highlight'
        sb = st.button('Speak with LARA')
        
        try:
            print(st.session_state.responses[session_key])
            pass
        except:
            st.session_state.responses[session_key] = None
            st.session_state.responses[session_key + "_check"] = False
        
        if sb:
            _ = record_audio_and_transcribe("daily_activities", session_key)
        else:
            display_question('What were the highlight of your day? Mention any interactions with family, friends, caregivers and any other important information.', 'Day Highlight', session_key)

    # Privacy and Security
    elif st.session_state.current_question == 4:
        st.subheader('Privacy and Security')
        st.write("Your diary entries are stored securely. You do not have to worry!")
        button_key = f"submit_button_{st.session_state.current_question}"
        if st.button('Submit Diary Entry', key=button_key):
            st.session_state.responses['Record Datetime'] = current_datetime
            save_daily_outputs(st.session_state.responses)
            st.session_state.daily_submitted = True

if st.session_state.daily_submitted:
    st.subheader('Thank you for providing today\'s diary entry!')
    with open(daily_file_path, 'rb') as file:
        daily_outputs = pickle.load(file)
    for k, v in daily_outputs.items():
        st.write(f"**{k.capitalize().replace('_', ' ')}:** {v}")
else:
    display_daily_form()
