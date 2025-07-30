from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from models.models import ParkingLot, ParkingSpot, Reservation, User
from app import db
from datetime import datetime

user = Blueprint('user', __name__, url_prefix='/user')

@user.before_request
def require_user():
    from flask import session, redirect, url_for, request, jsonify
    if not session.get('user_id') or session.get('role') != 'user':
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'not authenticate\d'}), 401
        return redirect(url_for('auth.login'))

@user.route('/dashboard')
def dashboard():
    search = request.args.get('search', '').strip()
    search_performed = 'search' in request.args
    if search:
        lots = ParkingLot.query.filter(
            (ParkingLot.prime_location_name.ilike(f'%{search}%')) |
            (ParkingLot.pin_code.ilike(f'%{search}%'))
        ).all()
    else:
        lots = []
    reservations = Reservation.query.filter_by(user_id=session.get('user_id')).all()
    return render_template('user/dashboard.html', lots=lots, reservations=reservations, search_performed=search_performed)

@user.route('/first_available_spot/<int:lot_id>')
def first_available_spot(lot_id):
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    return jsonify({
        'spot_id': spot.id if spot else '',
        'user_id': session.get('user_id')
    })

@user.route('/reserve/<int:lot_id>', methods=['POST'])
def reserve(lot_id):
    data = request.get_json()
    spot_id = data.get('spot_id')
    vehicle_number = data.get('vehicle_number')
    spot = ParkingSpot.query.filter_by(id=spot_id, lot_id=lot_id, status='A').first()
    if not spot:
        return jsonify({'success': False, 'message': 'The spot is not available'})
    spot.status = 'O'
    reservation = Reservation(
        spot_id=spot.id,
        user_id=session.get('user_id'),
        parking_timestamp=datetime.utcnow(),
        vehicle_number=vehicle_number
    )
    db.session.add(reservation)
    db.session.commit()
    return jsonify({'success': True})

@user.route('/release_info/<int:reservation_id>')
def release_info(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    return jsonify({
        'spot_id': reservation.spot_id,
        'vehicle_number': getattr(reservation, 'vehicle__number', ''),
        'parking_time': reservation.parking_timestamp.strftime('%Y-%m-%d %H:%M'),
        'releasing_time': reservation.leaving_timestamp.strftime('%Y-%m-%d %H:%M') if reservation.leaving_timestamp else '-',
        'total_cost': reservation.parking_cost or '-'
    })

@user.route('/release/<int:reservation_id>', methods=['POST'])
def release(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != session.get('user_id') or reservation.leaving_timestamp:
        return jsonify({'success': False, 'message': 'invalid operation'})
    reservation.leaving_timestamp = datetime.utcnow()
    lot = reservation.spot.lot
    duration = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600
    reservation.parking_cost = round(duration * lot.price, 2)
    reservation.spot.status = 'A'
    db.session.commit()
    print(f"[DEBUG] Spot {reservation.spot.id} status after park out: {reservation.spot.status}")
    return jsonify({
        'success': True,
        'total_cost': reservation.parking_cost,
        'parking_time': reservation.parking_timestamp.strftime('%Y-%m-%d %H:%M'),
        'releasing_time': reservation.leaving_timestamp.strftime('%Y-%m-%d %H:%M')
    })

@user.route('/search', methods=['GET'])
def search():
    search = request.args.get('search', '').strip()
    lots = []
    search_performed = False
    if search:
        lots = ParkingLot.query.filter(
            (ParkingLot.prime_location_name.ilike(f'%{search}%')) |
            (ParkingLot.pin_code.ilike(f'%{search}%'))
        ).all()
        search_performed = True
    elif 'search' in request.args:
        search_performed = True
    return render_template('user/search.html', lots=lots, search_performed=search_performed)

@user.route('/profile_info')
def profile_info():
    user = User.query.filter_by(id=session.get('user_id'), role='user').first()
    return {
        'full_name': user.full_name if user else '',
        'email': user.email if user else '',
        'address': user.address if user else '',
        'pin_code': user.pin_code if user else ''
    }

@user.route('/edit_profile', methods=['POST'])
def edit_profile():
    data = request.get_json()
    user = User.query.filter_by(id=session.get('user_id'), role='user').first()
    if not user:
        return {'success': False, 'message': 'User not found.'}
    user.full_name = data.get('full_name', user.full_name)
    user.email = data.get('email', user.email)
    user.address = data.get('address', user.address)
    user.pin_code = data.get('pin_code', user.pin_code)
    if data.get('new_password'):
        user.set_password(data['new_password'])
    db.session.commit()
    return {'success': True}

@user.route('/summary_data')
def summary_data():
    user_id = session.get('user_id')
    lots = ParkingLot.query.all()
    labels = [lot.prime_location_name for lot in lots]
    data = []
    for lot in lots:
        count = 0
        for spot in lot.spots:
            count += Reservation.query.filter_by(spot_id=spot.id, user_id=user_id).count()
        data.append(count)
    return jsonify({'labels': labels, 'data': data, 'label': 'your reservations'})


