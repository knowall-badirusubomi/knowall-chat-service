import os
from flask_caching import Cache
import redis
from flask import Flask, jsonify, request, application
from flask_socketio import SocketIO, disconnect, emit
import subprocess
from werkzeug.wrappers import Request, Response, ResponseStream
from jwt import (
    JWT,
    jwk_from_dict,
    jwk_from_pem,
)
from jwt.exceptions import (ExpiredSignatureError, InvalidTokenError)


        

class ChatFlaskApp(Flask):
    def __init__(self, name, jwtInstance):
        super().__init__(name)
        self.name = name
        self.jwtInstance = jwtInstance
        self.jwtSecret = os.environ["JWT_SECRET_KEY"]

        app.wsgi_app = AuthMiddleware(app.wsgi_app)
        app.config['CACHE_TYPE'] = 'redis'
        app.config['CACHE_REDIS_HOST'] = 'localhost'
        app.config['CACHE_REDIS_PORT'] = 6379
        app.config['CACHE_REDIS_DB'] = 0


class AuthMiddleware:
     
    def __init__(self, app: ChatFlaskApp, cache):
        self.app = app
        self.cache = cache

    def __call__(self, environ, start_response):
        request = Request(environ)
        token = request.authorization['x-access-key']

        '''Check cache for valid jwt'''
        authorized = True

        try:
            header_data = self.app.jwtInstance.get_unverified_header(token)
            payload = self.app.jwtInstance.decode(
                token,
                key=self.app.jwtSecret,
                algorithms=[header_data['alg'], ]
            )
            return self.app(environ, start_response)
        except ExpiredSignatureError as error:
            res = Response(u'Invalid access key', mimetype='text/plain', status=401)
            return res(environ, start_response)


@application.route('/chats/', methods=['GET'])
@cache.cached(timeout=60, key_prefix='items')
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

@application.route('/chats/:sessionId', methods=['POST'])
def add_item():
      # Get the item name from the request body
      item_name = request.json.get('userPrompt')

      # Add the item to the database here
      # ...

      # Delete the cached response to invalidate the cache
      cache.delete('items')

      return jsonify({'message': 'Item added successfully'})

@socketio.on("chat")
def handleChat(data):

    if request.sid not in {"sdsd":"sdsd"}:
        print("Agent not authenticated, disconnecting.")
        socketio.emit("unauthorized", room=request.sid)
        return disconnect()
    # Some logic here
    emit("chatResponse", data, broadcast=True)

@socketio.on("connect")
def onConnect():
    print("An agent is trying to connect...")
    # You can also put an initial check here if you need to authenticate on connection itself


@socketio.on("authenticate")
def authenticate(data):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        print("No auth header provided")
        return disconnect()

    token = auth_header.split("Bearer ")[-1]  # Extract token

    try:
        user_data = app.jwtInstance.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])
        emit('authenticated', room=request.id)
    except ExpiredSignatureError:
        print("Token expired")
        socketio.emit("unauthorized", room=request.sid)
        return disconnect()
    except InvalidTokenError:
        print("Invalid token")
        socketio.emit("unauthorized", room=request.sid)
        return disconnect()


class Session:
    def __init__(self, id=0):
        self.id = id




if __name__ =='__main__':

    # Initialize Redis client
    redis_client = redis.Redis(host='localhost', port=6379, db=0)

    jwtInstance = JWT()
    app = ChatFlaskApp(__name__, jwtInstance)
    socketio = SocketIO(app,debug=True,cors_allowed_origins='*',async_mode='eventlet')

    #Temp DB
    Chats = {}

    # Initialize Flask-Caching with Redis
    cache  = Cache(app=app)
    cache.init_app(app)

    
    #Start Server
    port = '8081'
    app.run('127.0.0.1', port, debug=True)
    print(f"Knowall chat service is live on port: {port}")