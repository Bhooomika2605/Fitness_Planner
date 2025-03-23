from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from google import genai
import json
import os
from datetime import datetime
import re
from pymongo import MongoClient
import secrets

# Initialize Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Initialize GenAI client
client = genai.Client(api_key="AIzaSyDMLx7XULAkS8gxhU2fXERJxHnzlt7BauU")

# # Initialize MongoDB connection
mongo_client = MongoClient("mongodb+srv://survebhoomika:Ch5E0WClHGyRFkP9@cluster0.1snpk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = mongo_client["fitness_tracker"]
users_collection = db["users"]

class UserProfile:
    def __init__(self, user_id):
        self.user_id = user_id
        self.profile_data = {}
        self.workout_history = []
        self.diet_history = []
        self.wellbeing_history = []
        self.load_profile()
    
    def load_profile(self):
        user_data = users_collection.find_one({"_id": self.user_id})
        if user_data:
            self.profile_data = user_data.get('profile', {})
            self.workout_history = user_data.get('workout_history', [])
            self.diet_history = user_data.get('diet_history', [])
            self.wellbeing_history = user_data.get('wellbeing_history', [])
    
    def save_profile(self):
        data = {
            "_id": self.user_id,
            'profile': self.profile_data,
            'workout_history': self.workout_history,
            'diet_history': self.diet_history,
            'wellbeing_history': self.wellbeing_history
        }
        # Using upsert=True to insert if not exists, update if exists
        users_collection.update_one({"_id": self.user_id}, {"$set": data}, upsert=True)
    
    def update_profile(self, profile_data):
        self.profile_data.update(profile_data)
        self.save_profile()
    
    def add_record(self, category, data):
        record = {
            'date': datetime.now().isoformat(),
            'data': data
        }
        if category == 'workout':
            self.workout_history.append(record)
        elif category == 'diet':
            self.diet_history.append(record)
        elif category == 'wellbeing':
            self.wellbeing_history.append(record)
        self.save_profile()

def generate_concise_workout_plan(user_profile):
    workout_params = user_profile.profile_data.get('workout', {})
    
    prompt = f"""
    Create a VERY CONCISE workout plan for a {workout_params.get('age', '30')}-year-old with 
    {workout_params.get('fitness_goals', 'general fitness')} goals. Format as follows using exactly these headings:
    
    TIME: Total minutes and frequency per week
    TYPE: Specify workout type (cardio, HIIT, strength, etc.)
    EXERCISES: List 5-7 specific exercises separated by semicolons (;) - include only the exercise names
    PRECAUTIONS: Brief safety notes
    
    Keep it under 100 words total. Format is critical - use the exact headings.
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt]
    )
    
    # Extract the text from the response
    response_text = response.text
    
    # Parse the response into structured data
    plan_data = {
        "time": "",
        "type": "",
        "exercises": [],
        "precautions": ""
    }
    
    # Better parsing with regular expressions
    time_match = re.search(r'TIME:\s*(.*?)(?:\n|$)', response_text)
    if time_match:
        plan_data["time"] = time_match.group(1).strip()
    
    type_match = re.search(r'TYPE:\s*(.*?)(?:\n|$)', response_text)
    if type_match:
        plan_data["type"] = type_match.group(1).strip()
    
    exercises_match = re.search(r'EXERCISES:\s*(.*?)(?:\n|$)', response_text)
    if exercises_match:
        exercises_text = exercises_match.group(1).strip()
        # Split by semicolons and strip whitespace
        plan_data["exercises"] = [ex.strip() for ex in exercises_text.split(';')]
    
    precautions_match = re.search(r'PRECAUTIONS:\s*(.*?)(?:\n|$)', response_text)
    if precautions_match:
        plan_data["precautions"] = precautions_match.group(1).strip()
    
    user_profile.add_record('workout', plan_data)
    return plan_data

def generate_concise_diet_plan(user_profile):
    workout_params = user_profile.profile_data.get('workout', {})
    diet_params = user_profile.profile_data.get('diet', {})
    
    prompt = f"""
    Create a VERY CONCISE diet plan for a {workout_params.get('age', '30')}-year-old with 
    {workout_params.get('fitness_goals', 'general fitness')} goals. Format as follows:
    
    1. CALORIES: Daily target
    2. DIET TYPE: (keto, low carb, high protein, etc.)
    3. INDIAN RECOMMENDATIONS: 3-4 specific meal suggestions
    4. MEAL TIMING: Brief eating schedule
    
    Respect dietary restrictions: {diet_params.get('dietary_restrictions', 'none')}
    Keep it under 100 words total.
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt]
    )
    
    # Extract the text from the response
    response_text = response.text
    
    # Parse the response into structured data
    plan_data = {
        "calories": "",
        "diet_type": "",
        "recommendations": [],
        "meal_timing": ""
    }
    
    # Better parsing with regular expressions
    calories_match = re.search(r'CALORIES:\s*(.*?)(?:\n|$)', response_text)
    if calories_match:
        plan_data["calories"] = calories_match.group(1).strip()
    
    diet_type_match = re.search(r'DIET TYPE:\s*(.*?)(?:\n|$)', response_text)
    if diet_type_match:
        plan_data["diet_type"] = diet_type_match.group(1).strip()
    
    recommendations_match = re.search(r'INDIAN RECOMMENDATIONS:\s*(.*?)(?:\n|$)', response_text)
    if recommendations_match:
        recommendations_text = recommendations_match.group(1).strip()
        # Split by commas or semicolons and strip whitespace
        plan_data["recommendations"] = [rec.strip() for rec in re.split(r'[;,]', recommendations_text)]
    
    meal_timing_match = re.search(r'MEAL TIMING:\s*(.*?)(?:\n|$)', response_text)
    if meal_timing_match:
        plan_data["meal_timing"] = meal_timing_match.group(1).strip()
    
    user_profile.add_record('diet', plan_data)
    return plan_data

def generate_concise_wellbeing_plan(user_profile):
    wellbeing_params = user_profile.profile_data.get('wellbeing', {})
    
    prompt = f"""
    Create a VERY CONCISE mental wellbeing plan for someone with {wellbeing_params.get('stress_level', 'medium')} stress.
    Format as follows using exactly these headings:
    
    MEDITATION: Brief technique and duration
    JOURNALING: Simple practice suggestion
    DAILY_PRACTICE: One key wellness habit
    
    Keep it under 75 words total. Format is critical - use the exact headings.
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt]
    )
    
    # Extract the text from the response
    response_text = response.text
    
    # Parse the response into structured data
    plan_data = {
        "meditation": "",
        "journaling": "",
        "daily_practice": ""
    }
    
    # Better parsing with regular expressions
    meditation_match = re.search(r'MEDITATION:\s*(.*?)(?:\n|$)', response_text)
    if meditation_match:
        plan_data["meditation"] = meditation_match.group(1).strip()
    
    journaling_match = re.search(r'JOURNALING:\s*(.*?)(?:\n|$)', response_text)
    if journaling_match:
        plan_data["journaling"] = journaling_match.group(1).strip()
    
    daily_practice_match = re.search(r'DAILY_PRACTICE:\s*(.*?)(?:\n|$)', response_text)
    if daily_practice_match:
        plan_data["daily_practice"] = daily_practice_match.group(1).strip()
    
    user_profile.add_record('wellbeing', plan_data)
    return plan_data

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        session['user_id'] = user_id
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_id = request.form['user_id']
        
        # Check if user already exists
        existing_user = users_collection.find_one({"_id": user_id})
        if existing_user:
            flash('User ID already exists. Please choose another one.')
            return redirect(url_for('register'))
        
        # Create new user profile
        user = UserProfile(user_id)
        
        # Collect and format user parameters
        workout_params = {
            "age": request.form['age'],
            "gender": request.form['gender'],
            "fitness_level": request.form['fitness_level'],
            "fitness_goals": request.form['fitness_goals'],
            "medical_conditions": request.form['medical_conditions'],
            "workout_duration": request.form['workout_duration'],
            "days_per_week": request.form['days_per_week']
        }
        
        diet_params = {
            "dietary_restrictions": request.form['dietary_restrictions'],
            "food_allergies": request.form['food_allergies']
        }
        
        wellbeing_params = {
            "stress_level": request.form['stress_level'],
            "sleep_quality": request.form['sleep_quality']
        }
        
        user_params = {
            "workout": workout_params,
            "diet": diet_params,
            "wellbeing": wellbeing_params
        }
        
        user.update_profile(user_params)
        session['user_id'] = user_id
        flash('Profile created successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    
    # Get the latest plans if available
    workout_plan = user.workout_history[-1]['data'] if user.workout_history else None
    diet_plan = user.diet_history[-1]['data'] if user.diet_history else None
    wellbeing_plan = user.wellbeing_history[-1]['data'] if user.wellbeing_history else None
    
    return render_template('dashboard.html', 
                          user=user,
                          workout_plan=workout_plan,
                          diet_plan=diet_plan,
                          wellbeing_plan=wellbeing_plan)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    
    if request.method == 'POST':
        # Update workout params
        workout_params = {
            "age": request.form['age'],
            "gender": request.form['gender'],
            "fitness_level": request.form['fitness_level'],
            "fitness_goals": request.form['fitness_goals'],
            "medical_conditions": request.form['medical_conditions'],
            "workout_duration": request.form['workout_duration'],
            "days_per_week": request.form['days_per_week']
        }
        
        # Update diet params
        diet_params = {
            "dietary_restrictions": request.form['dietary_restrictions'],
            "food_allergies": request.form['food_allergies']
        }
        
        # Update wellbeing params
        wellbeing_params = {
            "stress_level": request.form['stress_level'],
            "sleep_quality": request.form['sleep_quality']
        }
        
        user_params = {
            "workout": workout_params,
            "diet": diet_params,
            "wellbeing": wellbeing_params
        }
        
        user.update_profile(user_params)
        flash('Profile updated successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('profile.html', user=user)

@app.route('/generate/workout')
def generate_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    workout_plan = generate_concise_workout_plan(user)
    flash('Workout plan generated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/generate/diet')
def generate_diet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    diet_plan = generate_concise_diet_plan(user)
    flash('Diet plan generated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/generate/wellbeing')
def generate_wellbeing():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    wellbeing_plan = generate_concise_wellbeing_plan(user)
    flash('Mental wellbeing plan generated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/generate/all')
def generate_all():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    generate_concise_workout_plan(user)
    generate_concise_diet_plan(user)
    generate_concise_wellbeing_plan(user)
    flash('All plans generated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = UserProfile(session['user_id'])
    return render_template('history.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)