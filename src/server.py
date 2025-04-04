import os
from flask_caching import Cache
import redis
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, disconnect, emit
import subprocess
from werkzeug.wrappers import Request, Response, ResponseStream
import jwt
from dotenv import load_dotenv



load_dotenv()  # take environment variables
JWT_SECRET_TOKEN = os.getenv('JWT_SECRET_TOKEN')
# Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0)

class ChatFlaskApp(Flask):
    def __init__(self, name):
        super().__init__(name)
        self.name = name
        self.jwtSecret = JWT_SECRET_TOKEN
        self.cache = Cache(app=self)

        self.wsgi_app = AuthMiddleware(self.wsgi_app, self.cache)
        self.config['CACHE_TYPE'] = 'redis'
        self.config['CACHE_REDIS_HOST'] = 'localhost'
        self.config['CACHE_REDIS_PORT'] = 6379
        self.config['CACHE_REDIS_DB'] = 0

class AuthMiddleware:
     
    def __init__(self, app, cache):
        self.app = app
        self.cache = cache

    def __call__(self, environ, start_response):
        request = Request(environ)
        token = request.authorization['x-access-key']

        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_TOKEN,
                algorithms=['HS256']
            )
            return self.app(environ, start_response)
        except Exception as error:
            res = Response(u'Invalid access key', mimetype='text/plain', status=401)
            return res(environ, start_response)




Chats = {}
app = ChatFlaskApp(__name__)
# cache  = Cache(app=app)
socketio = SocketIO(app,debug=True,cors_allowed_origins='*',async_mode='gevent')
# Initialize Flask-Caching with Redis


@app.route('/chats/', methods=['GET'])
@app.cache.cached(timeout=60, key_prefix='items')
def get_chats():
      # Check if the response is already cached
      cached_response = redis_client.get('chats')
      if cached_response:
          return jsonify(cached_response)

      # Get the items from the database here
      items = Chats.query.all()

      # Serialize the items to JSON
      serialized_items = [item.to_dict() for item in items]

      response = jsonify(serialized_items)

      return response

    #   return jsonify({'message': 'Chats retrieved successfully'})



def validateToken(token):
    try:
        decoded = jwt.decode(token, JWT_SECRET_TOKEN, algorithms=["HS256"])
        return True
    except Exception as e:
        print('Invalid Token')
        return False



@app.route('/chats/:sessionId', methods=['POST'])
def add_item():
      # Get the item name from the request body
      item_name = request.json.get('userPrompt')

      # Add the item to the database here
      # ...

      # Delete the cached response to invalidate the cache
      app.cache.delete('items')

      return jsonify({'message': 'Item added successfully'})


def authmiddleware(fn):
    def middleware(*args):
        if validateToken(request.authorization.token):
            fn(*args)
        else:
            fn(False)
    
    return middleware


@socketio.on("chat")
@authmiddleware
def handleChat(data):
    # agentSession = redis_client.hgetall(f"agent-session:{request.sid}")
    if type(data) == bool and data == False:
        print("Agent not authenticated, disconnecting.")
        socketio.emit("unauthorized", room=request.sid)
        return disconnect()
    else:
        response = f"Server response to: {data['message']}"
    # Some logic here
    emit("chatResponse", {'response': response}, room=request.sid)

@socketio.on("connect")
def onConnect():
    print("An agent is trying to connect...")
    # You can also put an initial check here if you need to authenticate on connection itself


@socketio.on("authenticate")
def authenticate():
    auth_token = request.authorization.token

    try:
        userData = jwt.decode(
                auth_token,
                key=app.jwtSecret,
                algorithms=['HS256']
            )
        redis_client.hset(f"agent-session:{request.sid}",mapping={"id": userData["id"], "email" : userData["email"]})
        emit('authenticated', room=request.sid)
        

    except Exception as e:
        print(f"Token expired\nError: {e}")
        socketio.emit("unauthorized", room=request.sid)
        return disconnect()




if __name__ =='__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    
    port = 8081
    #Start Server
    server = pywsgi.WSGIServer(('0.0.0.0', port), app, handler_class=WebSocketHandler)
    server.serve_forever()
    # app.run('127.0.0.1', port, debug=True)
    print(f"Knowall chat service is live on port: {port}")