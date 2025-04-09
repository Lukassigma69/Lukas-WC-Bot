from flask import Flask

app = Flask(__name__)

# Define your Flask app route(s)
@app.route('/')
def home():
    return "Hello, World!"

# Function to run the Flask app
def run_flask():
    app.run()

# Somewhere in your code, you are using a Thread to run Flask
if __name__ == "__main__":
    from threading import Thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    # Continue with your other code if needed
