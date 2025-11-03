from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app import db
from models import Booking, Room, User
import os
class BookingService:
    
    @staticmethod
    def _get_expired_threshold():
        return datetime.now(timezone.utc) - timedelta(minutes=int(os.getenv('BOOKING_HOLD_MINUTES', 5)))
    
    @staticmethod
    def _parse_datetime(dt):
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    @staticmethod
    def retrieve_user(username, email):
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return existing_user
        user = User(username=username, email=email, password='')
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def retrieve_booking(booking_id):
        result = (
            db.session.query(Booking, User, Room)
            .join(User, Booking.user_id == User.id)
            .join(Room, Booking.room_id == Room.id)
            .filter(Booking.id == booking_id)
            .first()
        )
        if not result:
            return None
        
        booking, user, room = result
        current_status = BookingService.determine_booking_status(booking)
        
        return {
            'id': booking.id,
            'room_id': booking.room_id,
            'user_id': booking.user_id,
            'start_date': booking.start_date.isoformat() if booking.start_date else None,
            'end_date': booking.end_date.isoformat() if booking.end_date else None,
            'status': current_status,
            'user_name': user.username,
            'user_email': user.email,
            'room_name': room.name,
            'room_description': room.description,
        }
    
    @staticmethod
    def determine_booking_status(booking):
        if booking.status == 'pending' and booking.created_at:
            created_at = booking.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < BookingService._get_expired_threshold():
                return 'expired'
        return booking.status
    
    @staticmethod
    def confirm_booking(booking_id):
        expired_threshold = BookingService._get_expired_threshold()
        booking = Booking.query.filter(
            Booking.id == booking_id,
            Booking.status == 'pending',
            Booking.created_at > expired_threshold
        ).first()
        if not booking:
            return {'error': 'Booking not found or not pending.'}
        booking.status = 'confirmed'
        db.session.commit()
        return {'success': 'Booking confirmed successfully.'}
      
      
    @staticmethod
    def cancel_booking(booking_id):
        booking = Booking.query.get(booking_id)
        if not booking:
            return {'error': 'Booking not found.'}
        
        now = datetime.now(timezone.utc)
        if booking.end_date:
            end_date = booking.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            if end_date < now:
                return {'error': 'Cannot cancel a booking after its end_date has passed.'}
        
        booking.status = 'cancelled'
        db.session.commit()
        return {'success': 'Booking cancelled successfully.'}
    
    @staticmethod
    def _validate_booking_dates(start_date, end_date):
        if not all([start_date, end_date]):
            return {'error': 'start_date and end_date are required.'}
        
        start_date = BookingService._parse_datetime(start_date)
        end_date = BookingService._parse_datetime(end_date)
        
        if not start_date or not end_date:
            return {'error': 'Invalid date format. Use ISO8601 (YYYY-MM-DDTHH:MM:SSZ)'}
        
        now = datetime.now(timezone.utc)
        if start_date >= end_date:
            return {'error': 'start_date must be before end_date.'}
        if start_date < now or end_date < now:
            return {'error': 'start_date and end_date must be in the future.'}
        
        return {'start_date': start_date, 'end_date': end_date}
    
    @staticmethod
    def _check_room_available(room_id, start_date, end_date):
        expired_threshold = BookingService._get_expired_threshold()
        blocking = Booking.query.filter(
            Booking.room_id == room_id,
            Booking.start_date < end_date,
            Booking.end_date > start_date,
            ((Booking.status == 'confirmed') |
             ((Booking.status == 'pending') & (Booking.created_at > expired_threshold)))
        ).first()
        return blocking is None
    
    @staticmethod
    def create_booking(room_id, user_name, user_email, start_date, end_date, status='pending'):
        if not all([room_id, user_name, user_email, start_date, end_date]):
            return {'error': 'room_id, user_name, user_email, start_date, and end_date are required.'}
        
        validation = BookingService._validate_booking_dates(start_date, end_date)
        if 'error' in validation:
            return validation
        
        start_date = validation['start_date']
        end_date = validation['end_date']
        
        room = Room.query.get(room_id)
        if not room:
            return {'error': 'Room does not exist.'}
        
        user = BookingService.retrieve_user(user_name, user_email)
        
        if not BookingService._check_room_available(room_id, start_date, end_date):
            return {'error': 'Room is not available for the selected time range.'}
        
        booking = Booking(room_id=room_id, user_id=user.id, start_date=start_date, end_date=end_date, status=status)
        db.session.add(booking)
        db.session.commit()
        return {'success': 'Booking created successfully.', 'booking_id': booking.id}

    @staticmethod
    def update_booking(booking_id, start_date, end_date, status):
        booking = Booking.query.get(booking_id)
        if not booking:
            return {'error': 'Booking not found.'}
        
        validation = BookingService._validate_booking_dates(start_date, end_date)
        if 'error' in validation:
            return validation
        
        start_date = validation['start_date']
        end_date = validation['end_date']
        
        if status in ['confirmed', 'pending']:
            if not BookingService._check_room_available(booking.room_id, start_date, end_date):
                return {'error': 'Room is not available for the selected time range.'}
        
        booking.start_date = start_date
        booking.end_date = end_date
        booking.status = status
        db.session.commit()
        return {'success': 'Booking updated successfully.', 'booking_id': booking.id}

    @staticmethod
    def release_booking(booking_id):
        booking = Booking.query.filter(Booking.id == booking_id, Booking.status == 'pending').first()
        if not booking:
            return {'error': 'Booking not found or not pending.'}
        booking.status = 'released'
        db.session.commit()
        return {'success': 'Booking released successfully.'}

    @staticmethod
    def get_available_rooms_by_date_range(start_date, end_date):
        sql = f"""
            SELECT r.id, r.name, r.description, r.price FROM room r WHERE NOT EXISTS (
                SELECT 1 FROM booking b
                WHERE b.room_id = r.id
                  AND b.start_date < :end_date
                  AND b.end_date > :start_date
                  AND (
                    b.status = 'confirmed'
                    OR (
                      b.status = 'pending'
                      AND b.created_at > DATETIME('now', '-{int(os.getenv('BOOKING_HOLD_MINUTES', 5))} minutes')
                    )
                  )
            )
        """
        result = db.session.execute(text(sql), {
            'start_date': start_date,
            'end_date': end_date,
        })
        rows = result.mappings().all()
        return [
            {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'price': row['price'],
            }
            for row in rows
        ]