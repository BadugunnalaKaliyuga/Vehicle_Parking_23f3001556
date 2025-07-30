from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from models.models import User, ParkingLot, ParkingSpot, Reservation
from app import db

admin = Blueprint('admin', __name__, url_prefix='/admin')
@admin.before_request
def require_admin():
    from flask import session, redirect, url_for
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

@admin.route('/dashboard')
def dashboard():
    if not session.get('role') == 'admin':
        return redirect(url_for('auth.login'))
    lots = ParkingLot.query.all()
    lot_names = []
    available_counts = []
    occupied_counts = []
    revenues = []
    for lot in lots:
        lot_names.append(lot.prime_location_name)
        available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available_counts.append(available)
        occupied_counts.append(occupied)
        revenue = db.session.query(db.func.sum(Reservation.parking_cost)).join(ParkingSpot).filter(ParkingSpot.lot_id==lot.id).scalar() or 0
        revenues.append(revenue)
    spots = ParkingSpot.query.all()
    users = User.query.filter(User.role == 'user').order_by(User.id).all()
    reservations = Reservation.query.all()
    return render_template(
        'admin/dashboard.html',
        lots=lots,
        spots=spots,
        users=users,
        reservations=reservations,
        lot_names=lot_names,
        available_counts=available_counts,
        occupied_counts=occupied_counts,
        revenues=revenues
    )

@admin.route('/lots', methods=['GET', 'POST'])
def lots():
    if request.method == 'POST':
        name = request.form['prime_location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pin_code = request.form['pin_code']
        max_spots = int(request.form['maximum_number_of_spots'])
        lot = ParkingLot(prime_location_name=name, price=price, address=address, pin_code=pin_code, maximum_number_of_spots=max_spots)
        db.session.add(lot)
        db.session.commit()
        for i in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)
        db.session.commit()
        flash('Parking lot created successfully')
        return redirect(url_for('admin.lots'))
    lots = ParkingLot.query.all()
    return render_template('admin/lots.html', lots=lots)

@admin.route('/add_lot', methods=['POST'])
def add_lot():
    try:
        data = request.get_json()
        lot = ParkingLot(
            prime_location_name=data['prime_location_name'],
            price=float(data['price']),
            address=data['address'],
            pin_code=data['pin_code'],
            maximum_number_of_spots=int(data['maximum_number_of_spots'])
        )
        db.session.add(lot)
        db.session.commit()
        
        for _ in range(lot.maximum_number_of_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin.route('/edit_lot', methods=['POST'])
def edit_lot():
    try:
        data = request.get_json()
        lot = ParkingLot.query.get_or_404(data['lot_id'])
        lot.prime_location_name = data['prime_location_name']
        lot.address = data['address']
        lot.pin_code = data['pin_code']
        lot.price = float(data['price'])
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin.route('/delete_lot', methods=['POST'])
def delete_lot():
    try:
        data = request.get_json()
        lot = ParkingLot.query.get_or_404(data['lot_id'])

        if any(spot.status != 'A' for spot in lot.spots):
            return jsonify({'success': False, 'message': 'cannor delete lot having a spot occupied'})
        for spot in lot.spots:
            db.session.delete(spot)
        db.session.delete(lot)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin.route('/users')
def users():
    users = User.query.filter(User.role == 'user').all()
    return render_template('admin/users.html', users=users)

@admin.route('/spots')
def spots():
    spots = ParkingSpot.query.all()
    return render_template('admin/spots.html', spots=spots)

@admin.route('/spot_details/<int:spot_id>')
def spot_details(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    return jsonify({
        'id': spot.id,
        'status': spot.status,
        'lot_id': spot.lot_id
    })

@admin.route('/delete_spot', methods=['POST'])
def delete_spot():
    try:
        data = request.get_json()
        spot = ParkingSpot.query.get_or_404(data['spot_id'])
        if spot.status != 'A':
            return jsonify({'success': False, 'message': 'Cannot delete occupied spot'})
        db.session.delete(spot)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin.route('/occupied_details/<int:spot_id>')
def occupied_details(spot_id):
    from datetime import datetime
    spot = ParkingSpot.query.get_or_404(spot_id)
    if spot.status == 'O':
        reservation = Reservation.query.filter_by(spot_id=spot.id, leaving_timestamp=None).first()
        if reservation:
            lot = spot.lot
            now = datetime.utcnow()
            duration = (now - reservation.parking_timestamp).total_seconds() / 3600
            est_cost = round(duration * lot.price, 2)
            return jsonify({
                'spot_id': spot.id,
                'user_id': reservation.user_id,
                'vehicle_number': getattr(reservation, 'vehicle_number', ''),
                'parking_time': reservation.parking_timestamp.strftime('%Y-%m-%d %H:%M'),
                'parking_cost': f"${est_cost:.2f} (est.)"
            })
    reservation = Reservation.query.filter_by(spot_id=spot.id).order_by(Reservation.id.desc()).first()
    if reservation and reservation.leaving_timestamp and reservation.parking_cost is not None:
        return jsonify({
            'spot_id': spot.id,
            'user_id': reservation.user_id,
            'vehicle_number': getattr(reservation, 'vehicle_number', ''),
            'parking_time': reservation.parking_timestamp.strftime('%Y-%m-%d %H:%M'),
            'parking_cost': f"${reservation.parking_cost:.2f}"
        })
    return jsonify({'error': 'no active reservation found'})

@admin.route('/summary_data')
def summary_data():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    lots = ParkingLot.query.all()
    labels = [lot.prime_location_name for lot in lots]
    
    revenue = []
    available = []
    occupied = []

    for lot in lots:
        lot_revenue = 0
        for spot in lot.spots:
            lot_revenue += sum(r.parking_cost or 0 for r in spot.reservations if r.parking_cost)
        revenue.append(lot_revenue)

        available.append(sum(1 for spot in lot.spots if spot.status == 'A'))
        occupied.append(sum(1 for spot in lot.spots if spot.status == 'O'))

    return jsonify({
        'labels': labels,
        'revenue': revenue,
        'available': available,
        'occupied': occupied
    })

@admin.route('/profile_info')
def profile_info():
    user = User.query.filter_by(id=session.get('user_id'), role='admin').first()
    return jsonify({
        'username': user.username if user else ''
    })

@admin.route('/edit_profile', methods=['POST'])
def edit_profile():
    try:
        data = request.get_json()
        user = User.query.filter_by(id=session.get('user_id'), role='admin').first()
        if not user:
            return jsonify({'success': False, 'message': 'user not found'})
        
        user.username = data.get('new_username', user.username)
        if data.get('new_password'):
            user.set_password(data['new_password'])
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


