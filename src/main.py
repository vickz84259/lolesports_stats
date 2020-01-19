from flask import Flask

app = Flask(__name__)


@app.route('/_ah/start')
def hello_world():
    return 'Hello, World!'


@app.route('/')
def index():
    return 'Home page'
