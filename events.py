from flask import request
from flask_socketio import emit, join_room, leave_room
import uuid
from datetime import datetime
from database import log_call
from models import users, active_calls


def register_events(socketio):
    @socketio.on('connect')
    def handle_connect():
        email = request.args.get('email')
        if email:
            users[email] = request.sid
            join_room(email)
            print(f"User {email} connected")

    @socketio.on('disconnect')
    def handle_disconnect():
        for email, sid in users.items():
            if sid == request.sid:
                del users[email]
                leave_room(email)
                print(f"User {email} disconnected")
                break

    @socketio.on('call_request')
    def handle_call_request(data):
        caller_email = data['caller_email']
        callee_email = data['callee_email']
        call_id = f"{caller_email}_{callee_email}_{str(uuid.uuid4())}"

        if callee_email in users:
            emit('incoming_call', {
                'caller_email': caller_email,
                'call_id': call_id
            }, room=callee_email)
            log_call(call_id, caller_email, callee_email, 'requested')
        else:
            emit('user_unavailable', {
                 'callee_email': callee_email}, room=caller_email)
            log_call(call_id, caller_email, callee_email, 'failed')

    @socketio.on('call_response')
    def handle_call_response(data):
        call_id = data['call_id']
        response = data['response']
        caller_email = data['caller_email']
        callee_email = data['callee_email']

        if response == 'accept':
            emit('call_accepted', {
                 'call_id': call_id, 'callee_email': callee_email}, room=caller_email)
            active_calls[call_id] = {'start_time': datetime.now(), 'participants': [
                caller_email, callee_email]}
            log_call(call_id, caller_email, callee_email, 'accepted',
                     start_time=active_calls[call_id]['start_time'])
        else:
            emit('call_rejected', {
                 'call_id': call_id, 'callee_email': callee_email}, room=caller_email)
            log_call(call_id, caller_email, callee_email, 'rejected')

    @socketio.on('ice_candidate')
    def handle_ice_candidate(data):
        target_email = data['target_email']
        if target_email in users:
            emit('ice_candidate', data, room=target_email)

    @socketio.on('offer')
    def handle_offer(data):
        target_email = data['target_email']
        if target_email in users:
            emit('offer', data, room=target_email)

    @socketio.on('answer')
    def handle_answer(data):
        target_email = data['target_email']
        if target_email in users:
            emit('answer', data, room=target_email)

    @socketio.on('end_call')
    def handle_end_call(data):
        target_email = data['target_email']
        call_id = data['call_id']
        caller_email = data['caller_email']

        if target_email in users:
            emit('call_ended', {
                 'caller_email': caller_email}, room=target_email)

        if call_id in active_calls:
            end_time = datetime.now()
            start_time = active_calls[call_id]['start_time']
            participants = active_calls[call_id]['participants']
            log_call(
                call_id, participants[0], participants[1], 'ended', start_time, end_time)
            del active_calls[call_id]
