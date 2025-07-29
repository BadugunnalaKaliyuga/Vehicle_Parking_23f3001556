from app import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin , db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(126), unique=True, nullable=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(60))
    address = db.Column(db.String(100))
    pin_code = db.Column(db.String(10))
    role = db.Column(db.String(9), nullable=False, default='user')
    reservations = db.relationship('Reservation', backref='user', lazy=True)
    def set_password(self, password):
        self.password = password
    def check_password(self, password):
        return self.password == password
    
class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(150), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    maximum_number_of_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime)
    parking_cost = db.Column(db.Float)
    vehicle_number = db.Column(db.String(32))

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')
    reservations = db.relationship('Reservation', backref='spot', lazy=True)
