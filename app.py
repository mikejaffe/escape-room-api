from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import os


app = Flask(__name__)

# Use absolute path for SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "data", "escaperoom-development.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Import models after db is created to avoid circular imports
from models import Room, Booking, User

@app.route('/')
def index():
    return 'Hello, World!'


@app.route('/api/v1/availability', methods=['GET'])
def availability():
    from booking_service import BookingService
    from datetime import timezone

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'start_date and end_date query params are required (ISO8601)'}), 400

    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO8601 (YYYY-MM-DDTHH:MM:SSZ)'}), 400

    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    if start_date >= end_date:
        return jsonify({'error': 'start_date must be before end_date'}), 400

    rooms = BookingService.get_available_rooms_by_date_range(start_date, end_date)
    return jsonify({'rooms': rooms})


@app.route('/api/v1/bookings', methods=['POST'])
def create_booking():
    from booking_service import BookingService
    data = request.json
    room_id = data.get('room_id')
    guest = data.get('guest', {})
    user_name = guest.get('name') if isinstance(guest, dict) else None
    user_email = guest.get('email') if isinstance(guest, dict) else None
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    booking = BookingService.create_booking(room_id, user_name, user_email, start_date, end_date)
    if booking.get('error'):
        return jsonify({'error': booking.get('error')}), 400
    return jsonify({'booking': booking})


@app.route('/api/v1/bookings/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    from booking_service import BookingService
    booking = BookingService.retrieve_booking(booking_id)
    if booking is None:
        return jsonify({'error': 'Booking not found'}), 404
    return jsonify({'booking': booking})

@app.route('/api/v1/bookings/<int:booking_id>/confirm', methods=['PUT'])
def confirm_booking(booking_id):
    from booking_service import BookingService
    data = request.json
    booking = BookingService.confirm_booking(booking_id)
    if booking.get('error'):
        return jsonify({'error': booking.get('error')}), 400
    return jsonify({'success': booking.get('success')})


@app.route('/api/v1/bookings/<int:booking_id>/cancel', methods=['DELETE'])
def cancel_booking(booking_id):
    from booking_service import BookingService
    booking = BookingService.cancel_booking(booking_id)
    if booking.get('error'):
        return jsonify({'error': booking.get('error')}), 400
    return jsonify({'success': booking.get('success')})


@app.route('/api/v1/bookings/<int:booking_id>/release', methods=['DELETE'])
def release_booking(booking_id):
    from booking_service import BookingService
    booking = BookingService.release_booking(booking_id)
    if booking.get('error'):
        return jsonify({'error': booking.get('error')}), 400
    return jsonify({'success': booking.get('success')})

@app.route('/api/v1/rooms')
def rooms():
    return jsonify({'rooms': [room.to_dict() for room in Room.query.all()]})

@app.route('/api/v1/rooms/<int:room_id>', methods=['GET'])
def room(room_id):
    return jsonify({'room': Room.query.get_or_404(room_id).to_dict()})

@app.route('/api/v1/bookings', methods=['GET'])
def bookings():
    return jsonify({'bookings': [booking.to_dict() for booking in Booking.query.all()]})

@app.route('/api/v1/bookings/<int:booking_id>')
def booking(booking_id):
    return jsonify({'booking': Booking.query.get_or_404(booking_id).to_dict()})

if __name__ == '__main__':
    app.run(debug=True)
