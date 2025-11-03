# Escape Room Booking API

A Flask-based REST API for booking escape room time slots with a 5-minute hold mechanism that allows teams to temporarily reserve a slot while coordinating with friends.

## Setup Instructions

### Prerequisites
- Python 3.12+
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mikejaffe/escape-room-api
cd escape-room-api
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
```bash
flask db upgrade
```

This will:
- Create all database tables
- Run the seed migration to populate rooms from `data/rooms.json`

5. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:5000`

### Running Tests

Run all tests:
```bash
pytest test_booking.py -v
```

## API Endpoints

### Get Available Rooms
```
GET /api/v1/availability?start_date=2025-11-04T10:00:00Z&end_date=2025-11-04T11:00:00Z
```

Returns available rooms for a given time range, excluding:
- Confirmed bookings that overlap
- Pending bookings created within the last 5 minutes

### Create Booking (Hold)
```
POST /api/v1/bookings
Content-Type: application/json

{
  "room_id": 1,
  "guest": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "start_date": "2025-11-04T10:00:00Z",
  "end_date": "2025-11-04T11:00:00Z"
}
```

Creates a pending booking (hold) that expires after 5 minutes.

### Confirm Booking
```
PUT /api/v1/bookings/{booking_id}/confirm
```

Converts a pending booking to confirmed. Fails if the booking has expired (>5 minutes old).

### Release Booking
```
DELETE /api/v1/bookings/{booking_id}/release
```

Releases a pending booking, making the room available again.

### Get Booking
```
GET /api/v1/bookings/{booking_id}
```

Returns booking details including user and room information. Shows `expired` status for pending bookings older than 5 minutes.

## Architecture Decisions

### Static Methods Service Class

Used a `BookingService` class with all static methods instead of instance methods or a module. Provides a clean namespace (`BookingService.create_booking()`) and is easy to test. Could be converted to a module if preferred, but the class provides good organization.

### SQLite Database

Used SQLite for simplicity and portability. No external dependencies required, fast for development, and sufficient for this task. For production, I'd prefer PostgreSQL with proper connection pooling.

### Raw SQL for Availability Query

Used raw SQL with `NOT EXISTS` for the availability check. More efficient than ORM queries with joins and clearer intent - "rooms without blocking bookings". Less portable than ORM, but can provide potentially better performance than in-memory arrays

### Double-Check Pattern for Race Conditions

Doing an availability check twice in `create_booking` - once before user creation, once right before commit. This prevents race conditions where two requests check availability simultaneously. The final check right before commit ensures no overlap. Simpler than database-level locking for this use case, though not perfect. For production, would use database-level locking (`SELECT FOR UPDATE`)  

### Status as String Field

Booking status stored as a string field (`pending`, `confirmed`, `cancelled`, `released`, `expired`). Simple and flexible, easy to add new statuses. The `expired` status is computed, not stored (determined by `created_at` timestamp).  

### Timezone Handling

All datetimes stored and compared in UTC. Consistent timezone handling, no DST issues, and standard practice for APIs. API consumers must handle timezone conversion, but this is standard practice.

## If I had more time....

### Authentication/Authorization

No user authentication system implemented. I'd use JWT tokens for stateless authentication, implement password hashing with bcrypt, and add middleware to validate tokens on protected routes using Flask-JWT-Extended. 

### Background Job for Expiration

Pending bookings expire based on query-time calculation, not automatic cleanup. I'd use Celery with Redis for background tasks, scheduling a job every minute to check for expired bookings and update their status.


### API Rate Limiting

No rate limiting on endpoints. I'd use Flask-Limiter with Redis backend.

### Comprehensive Error Handling

Basic error handling exists, but could be more comprehensive.

### Database Migrations for Production

Migrations exist but not optimized for no-downtime deployments. 

## AI Tools Used

**Tools:** Cursor AI (Claude-based assistant)

While I did use Cursor, all archetecure decisions and code implementaiton (other than some tests) were written myself.

**How They Helped:**
1. **Refactoring:** Helped extract common patterns and reduce duplication
2. **Test Writing:** Generated some test cases to speed up development time 
3. **README** Spell check and formatting
 

