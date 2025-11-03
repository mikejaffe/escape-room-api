import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from app import app, db
from models import Room, Booking, User
from booking_service import BookingService


@pytest.fixture(scope='function')
def app_context():
    db_fd, db_path = tempfile.mkstemp(suffix='booking_test.db')
    os.close(db_fd)
    
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        room = Room(id=1, name='Test Room', description='Test Description', price=50.0)
        db.session.add(room)
        db.session.commit()
        yield
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
    
    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestHoldSystem:
    
    def test_pending_booking_expires_after_5_minutes(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6)
        )
        db.session.add(booking)
        db.session.commit()
        
        status = BookingService.determine_booking_status(booking)
        assert status == 'expired'
        
        available = BookingService.get_available_rooms_by_date_range(start, end)
        assert any(r['id'] == 1 for r in available)
    
    def test_pending_booking_within_5_minutes_still_active(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = future_start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=future_start,
            end_date=future_end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=3)
        )
        db.session.add(booking)
        db.session.commit()
        
        status = BookingService.determine_booking_status(booking)
        assert status == 'pending'
        
        available_rooms = BookingService.get_available_rooms_by_date_range(future_start, future_end)
        assert not any(room['id'] == 1 for room in available_rooms)


class TestConfirmRelease:
    
    def test_confirm_pending_booking(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2)
        )
        db.session.add(booking)
        db.session.commit()
        
        result = BookingService.confirm_booking(booking.id)
        assert 'success' in result
        
        db.session.refresh(booking)
        assert booking.status == 'confirmed'
    
    def test_confirm_expired_booking_fails(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = future_start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=future_start,
            end_date=future_end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6)
        )
        db.session.add(booking)
        db.session.commit()
        
        result = BookingService.confirm_booking(booking.id)
        assert 'error' in result
        assert 'not found or not pending' in result['error']
    
    def test_release_pending_booking(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2)
        )
        db.session.add(booking)
        db.session.commit()
        
        result = BookingService.release_booking(booking.id)
        assert 'success' in result
        
        b = Booking.query.get(booking.id)
        assert b.status == 'released'
        
        available = BookingService.get_available_rooms_by_date_range(start, end)
        assert any(r['id'] == 1 for r in available)
    
    def test_release_confirmed_booking_fails(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='confirmed',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2)
        )
        db.session.add(booking)
        db.session.commit()
        
        result = BookingService.release_booking(booking.id)
        assert 'error' in result
        assert 'not found or not pending' in result['error']


class TestRaceCondition:
    
    def test_concurrent_bookings_prevent_double_booking(self, app_context):
        user1 = User(username='user1', email='user1@example.com', password='')
        user2 = User(username='user2', email='user2@example.com', password='')
        db.session.add_all([user1, user2])
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        result1 = BookingService.create_booking(
            1, 'user1', 'user1@example.com', 
            start.isoformat(), end.isoformat()
        )
        assert 'success' in result1 or 'booking_id' in result1
        
        result2 = BookingService.create_booking(
            1, 'user2', 'user2@example.com',
            start.isoformat(), end.isoformat()
        )
        assert 'error' in result2
        assert 'not available' in result2['error'].lower()
    
    def test_race_condition_double_check_prevents_overlap(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking1 = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.session.add(booking1)
        db.session.commit()
        
        result = BookingService.create_booking(
            1, 'user2', 'user2@example.com',
            start.isoformat(), end.isoformat()
        )
        assert 'error' in result
        assert 'not available' in result['error'].lower()


class TestBookingFlow:
    
    def test_create_pending_booking(self, app_context):
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        result = BookingService.create_booking(
            1, 'Test User', 'test@example.com',
            start.isoformat(), end.isoformat()
        )
        
        assert 'success' in result or 'booking_id' in result
        
        booking = Booking.query.filter_by(room_id=1).first()
        assert booking is not None
        assert booking.status == 'pending'
    
    def test_retrieve_booking_shows_expired_status(self, app_context):
        user = User(username='testuser', email='test@example.com', password='')
        db.session.add(user)
        db.session.commit()
        
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(hours=1)
        
        booking = Booking(
            room_id=1,
            user_id=user.id,
            start_date=start,
            end_date=end,
            status='pending',
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6)
        )
        db.session.add(booking)
        db.session.commit()
        
        result = BookingService.retrieve_booking(booking.id)
        assert result is not None
        assert result['status'] == 'expired'

