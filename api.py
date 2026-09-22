from flask import Flask, jsonify, request

app = Flask(__name__)

# 1. A simple GET endpoint
@app.route('/api/hello', methods=['GET'])
def say_hello():
    return jsonify({
        "status": "success",
        "message": "Hello, World!"
    })

# 2. A POST endpoint that accepts data
@app.route('/api/data', methods=['POST'])
def receive_data():
    # request.json automatically parses the incoming JSON payload
    data = request.json
    
    if not data or 'name' not in data:
        # Return a 400 Bad Request status code
        return jsonify({"error": "Please provide a name"}), 400
        
    return jsonify({
        "message": f"Data received for {data['name']}",
        "received_data": data
    }), 201

if __name__ == '__main__':
    # Run the server on port 5001 to avoid conflicting with your main app.py on port 5000
    app.run(debug=True, port=5001)
