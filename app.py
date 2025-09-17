from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import pika
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key'

# MongoDB Configuration
app.config['MONGO_URI'] = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_watering'
mongo = PyMongo(app)

# RabbitMQ Configuration
RABBITMQ_HOST = 'rmq-smart-watering.sta.my.id'
RABBITMQ_USER = 'smart-watering'
RABBITMQ_PASSWORD = 'mBW8L8kSGYPiri8B'
RABBITMQ_VHOST = '/smart-watering'

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'danger')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Home route
@app.route('/')
def index():
    if 'user_id' in session:
        user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        farms = list(mongo.db.farms.find({'user_id': ObjectId(session['user_id'])}))
        devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id'])}))
        return render_template('index.html', user=user, farms=farms, devices=devices)
    return render_template('index.html')

@app.route('/home')
@login_required
def home():
    # Pengecekan 'user_id' di session sudah ditangani oleh @login_required
    user_id = ObjectId(session['user_id'])
    
    user = mongo.db.users.find_one({'_id': user_id})
    
    # Ambil daftar lahan untuk ditampilkan di peta
    farms = list(mongo.db.farms.find({'user_id': user_id}))
    
    # Hitung jumlah data menggunakan count_documents agar lebih efisien
    farms_count = mongo.db.farms.count_documents({'user_id': user_id})
    devices_count = mongo.db.devices.count_documents({'user_id': user_id})
    # Sesuai label di HTML "Jadwal Aktif", kita hanya hitung yang 'enabled'
    schedules_count = mongo.db.schedules.count_documents({'user_id': user_id, 'enabled': True})
    
    return render_template('dashboard.html', 
                           user=user, 
                           farms=farms, 
                           farms_count=farms_count,
                           devices_count=devices_count,
                           schedules_count=schedules_count)

# Auth routes
@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = mongo.db.users.find_one({'email': email})
        if user and user['password'] == password:  # In production, use password hashing
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['name'] = user['name']
            flash('Login berhasil!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Email atau password salah!', 'danger')
    
    return render_template('auth/login.html')

@app.route('/auth/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Password dan konfirmasi password tidak cocok!', 'danger')
            return redirect(url_for('register'))
        
        if mongo.db.users.find_one({'email': email}):
            flash('Email sudah terdaftar!', 'danger')
            return redirect(url_for('register'))
        
        user_id = mongo.db.users.insert_one({
            'name': name,
            'email': email,
            'password': password,  # In production, hash the password
            'created_at': datetime.utcnow()
        }).inserted_id
        
        session['user_id'] = str(user_id)
        session['email'] = email
        session['name'] = name
        flash('Registrasi berhasil!', 'success')
        return redirect(url_for('auth/login.html'))
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

# Profile routes
@app.route('/profile')
@login_required
def profile():
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    print("profile")
    return render_template('profile/profile.html', user=user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        
        mongo.db.users.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$set': {
                'name': name,
                'email': email
            }}
        )
        
        session['name'] = name
        session['email'] = email
        flash('Profil berhasil diperbarui!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile/edit_profile.html', user=user)

@app.route('/profile/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        
        if user['password'] != current_password:
            flash('Password saat ini salah!', 'danger')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('Password baru dan konfirmasi password tidak cocok!', 'danger')
            return redirect(url_for('change_password'))
        
        mongo.db.users.update_one(
            {'_id': ObjectId(session['user_id'])},
            {'$set': {'password': new_password}}
        )
        
        flash('Password berhasil diubah!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile/change_password.html')

# Farm routes
@app.route('/farm')
@login_required
def farms():
    farms_list = list(mongo.db.farms.find({'user_id': ObjectId(session['user_id'])}))
    return render_template('farm/farms.html', farms=farms_list)

@app.route('/farm/add', methods=['GET', 'POST'])
@login_required
def add_farm():
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        area = request.form.get('area')
        crop_type = request.form.get('crop_type')
        
        mongo.db.farms.insert_one({
            'user_id': ObjectId(session['user_id']),
            'name': name,
            'location': location,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'area': area,
            'crop_type': crop_type,
            'created_at': datetime.utcnow()
        })
        
        flash('Lahan berhasil ditambahkan!', 'success')
        return redirect(url_for('farms'))
    
    return render_template('farm/add_farm.html')

@app.route('/farm/<farm_id>')
@login_required
def farm_detail(farm_id):
    farm = mongo.db.farms.find_one({'_id': ObjectId(farm_id), 'user_id': ObjectId(session['user_id'])})
    if not farm:
        flash('Lahan tidak ditemukan!', 'danger')
        return redirect(url_for('farms'))
    
    devices = list(mongo.db.devices.find({'farm_id': ObjectId(farm_id)}))
    return render_template('farm/farm_detail.html', farm=farm, devices=devices)

@app.route('/farm/<farm_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_farm(farm_id):
    farm = mongo.db.farms.find_one({'_id': ObjectId(farm_id), 'user_id': ObjectId(session['user_id'])})
    if not farm:
        flash('Lahan tidak ditemukan!', 'danger')
        return redirect(url_for('farms'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        area = request.form.get('area')
        crop_type = request.form.get('crop_type')
        
        mongo.db.farms.update_one(
            {'_id': ObjectId(farm_id)},
            {'$set': {
                'name': name,
                'location': location,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'area': area,
                'crop_type': crop_type
            }}
        )
        
        flash('Lahan berhasil diperbarui!', 'success')
        return redirect(url_for('farms'))
    
    return render_template('farm/edit_farm.html', farm=farm)

@app.route('/farm/<farm_id>/delete')
@login_required
def delete_farm(farm_id):
    farm = mongo.db.farms.find_one({'_id': ObjectId(farm_id), 'user_id': ObjectId(session['user_id'])})
    if not farm:
        flash('Lahan tidak ditemukan!', 'danger')
        return redirect(url_for('farms'))
    
    # Check if farm has devices
    devices_count = mongo.db.devices.count_documents({'farm_id': ObjectId(farm_id)})
    if devices_count > 0:
        flash('Tidak dapat menghapus lahan yang masih memiliki perangkat!', 'danger')
        return redirect(url_for('farms'))
    
    mongo.db.farms.delete_one({'_id': ObjectId(farm_id)})
    flash('Lahan berhasil dihapus!', 'success')
    return redirect(url_for('farms'))

# Device routes
# @app.route('/device')
# @login_required
# def devices():
#     devices_list = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id'])}))
#     farms = list(mongo.db.farms.find({'user_id': ObjectId(session['user_id'])}))
    
#     # Convert farms to dict for easy access
#     farms_dict = {str(farm['_id']): farm for farm in farms}
    
#     return render_template('device/devices.html', devices=devices_list, farms=farms_dict)

# app.py

@app.route('/device')
@login_required
def devices():
    user_id = ObjectId(session['user_id'])
    devices_list = list(mongo.db.devices.find({'user_id': user_id}))
    farms = list(mongo.db.farms.find({'user_id': user_id}))
    
    # Convert farms to dict for easy access
    farms_dict = {str(farm['_id']): farm for farm in farms}
    
    # ================== BLOK BARU DIMULAI DI SINI ==================
    # Ambil data sensor terakhir untuk setiap perangkat menggunakan aggregation
    
    pipeline = [
        # 1. Urutkan semua data berdasarkan timestamp, dari yang terbaru
        {'$sort': {'timestamp': -1}},
        # 2. Kelompokkan berdasarkan device_id dan ambil data pertama (yang terbaru)
        {'$group': {
            '_id': '$device_id',
            'latest_record': {'$first': '$$ROOT'}
        }}
    ]
    
    latest_data_cursor = mongo.db.sensor_data.aggregate(pipeline)
    
    # Buat dictionary untuk akses mudah di template: { 'device_id_string': { ... record ... } }
    latest_data_dict = {}
    for item in latest_data_cursor:
        # Konversi semua tipe data agar JSON serializable
        record = item['latest_record']
        record['_id'] = str(record['_id'])
        record['user_id'] = str(record['user_id'])
        record['device_id'] = str(record['device_id'])
        record['timestamp'] = record['timestamp'].isoformat()
        latest_data_dict[str(item['_id'])] = record
        
    # =================== BLOK BARU SELESAI DI SINI ===================

    return render_template('device/devices.html', 
                           devices=devices_list, 
                           farms=farms_dict,
                           latest_data=latest_data_dict) # Kirim data terakhir ke template

@app.route('/device/add', methods=['GET', 'POST'])
@login_required
def add_device():
    farms = list(mongo.db.farms.find({'user_id': ObjectId(session['user_id'])}))
    
    if request.method == 'POST':
        name = request.form.get('name')
        device_type = request.form.get('type')
        farm_id = request.form.get('farm_id')
        topic = request.form.get('topic')
        description = request.form.get('description')
        
        mongo.db.devices.insert_one({
            'user_id': ObjectId(session['user_id']),
            'farm_id': ObjectId(farm_id),
            'name': name,
            'type': device_type,
            'topic': topic,
            'description': description,
            'status': 'off',
            'created_at': datetime.utcnow()
        })
        
        flash('Perangkat berhasil ditambahkan!', 'success')
        return redirect(url_for('devices'))
    
    return render_template('device/add_device.html', farms=farms)

# @app.route('/device/<device_id>')
# @login_required
# def device_detail(device_id):
#     device = mongo.db.devices.find_one({'_id': ObjectId(device_id), 'user_id': ObjectId(session['user_id'])})
#     if not device:
#         flash('Perangkat tidak ditemukan!', 'danger')
#         return redirect(url_for('devices'))
    
#     farm = mongo.db.farms.find_one({'_id': device['farm_id']})
    
#     # Get latest sensor data
#     sensor_data = list(mongo.db.sensor_data.find({'device_id': ObjectId(device_id)}))
    
#     return render_template('device/device_detail.html', device=device, farm=farm, sensor_data=sensor_data)

# app.py

@app.route('/device/<device_id>')
@login_required
def device_detail(device_id):
    device = mongo.db.devices.find_one({'_id': ObjectId(device_id), 'user_id': ObjectId(session['user_id'])})
    if not device:
        flash('Perangkat tidak ditemukan!', 'danger')
        return redirect(url_for('devices'))
    
    farm = mongo.db.farms.find_one({'_id': device['farm_id']})
    
    sensor_data_cursor = mongo.db.sensor_data.find({'device_id': ObjectId(device_id)}) \
                                              .sort('timestamp', -1) \
                                              .limit(50)
    
    # ================== BLOK PERBAIKAN DIMULAI DI SINI ==================
    
    sensor_data = []
    for record in sensor_data_cursor:
        # Ubah setiap ObjectId dan datetime menjadi string
        record['_id'] = str(record['_id'])
        record['user_id'] = str(record['user_id'])
        record['device_id'] = str(record['device_id'])
        # Konversi timestamp ke format ISO yang standar untuk JavaScript
        record['timestamp'] = record['timestamp'].isoformat()
        sensor_data.append(record)

    # =================== BLOK PERBAIKAN SELESAI DI SINI ===================
    
    return render_template('device/device_detail.html', 
                           device=device, 
                           farm=farm, 
                           sensor_data=sensor_data)

@app.route('/device/<device_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_device(device_id):
    device = mongo.db.devices.find_one({'_id': ObjectId(device_id), 'user_id': ObjectId(session['user_id'])})
    if not device:
        flash('Perangkat tidak ditemukan!', 'danger')
        return redirect(url_for('devices'))
    
    farms = list(mongo.db.farms.find({'user_id': ObjectId(session['user_id'])}))
    
    if request.method == 'POST':
        name = request.form.get('name')
        device_type = request.form.get('type')
        farm_id = request.form.get('farm_id')
        topic = request.form.get('topic')
        description = request.form.get('description')
        
        mongo.db.devices.update_one(
            {'_id': ObjectId(device_id)},
            {'$set': {
                'name': name,
                'type': device_type,
                'farm_id': ObjectId(farm_id),
                'topic': topic,
                'description': description
            }}
        )
        
        flash('Perangkat berhasil diperbarui!', 'success')
        return redirect(url_for('devices'))
    
    return render_template('device/edit_device.html', device=device, farms=farms)

@app.route('/device/<device_id>/delete')
@login_required
def delete_device(device_id):
    device = mongo.db.devices.find_one({'_id': ObjectId(device_id), 'user_id': ObjectId(session['user_id'])})
    if not device:
        flash('Perangkat tidak ditemukan!', 'danger')
        return redirect(url_for('devices'))
    
    mongo.db.devices.delete_one({'_id': ObjectId(device_id)})
    flash('Perangkat berhasil dihapus!', 'success')
    return redirect(url_for('devices'))

@app.route('/device/<device_id>/control/<command>')
@login_required
def control_device(device_id, command):
    device = mongo.db.devices.find_one({'_id': ObjectId(device_id), 'user_id': ObjectId(session['user_id'])})
    if not device:
        return jsonify({'success': False, 'message': 'Perangkat tidak ditemukan!'})
    
    # Send command to RabbitMQ
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            virtual_host=RABBITMQ_VHOST,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        message = {
            'device_id': device_id,
            'command': command,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        channel.basic_publish(
            exchange='',
            routing_key=device['topic'],
            body=json.dumps(message)
        )
        
        connection.close()
        
        # Update device status in database
        mongo.db.devices.update_one(
            {'_id': ObjectId(device_id)},
            {'$set': {'status': command}}
        )

        # 3. DITAMBAHKAN: Simpan riwayat aksi manual ke database
        # Di dalam fungsi control_device di app.py

# DITAMBAHKAN: Simpan riwayat aksi manual ke koleksi sensor_data
        mongo.db.sensor_data.insert_one({
            'user_id': ObjectId(session['user_id']),
            'device_id': ObjectId(device_id),
            'timestamp': datetime.utcnow(),
            'action': command,      # Menyimpan aksi (on/off)
            'source': 'manual',     # Menandakan sumber aksi
            'temperature': None,    # Tidak ada data sensor untuk aksi ini
            'humidity': None,       # Tidak ada data sensor untuk aksi ini
            # 'moisture': None        # Tidak ada data sensor untuk aksi ini
        })
        
        return jsonify({'success': True, 'message': f'Perintah {command} berhasil dikirim!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Schedule routes
@app.route('/schedule')
@login_required
def schedules():
    schedules_list = list(mongo.db.schedules.find({'user_id': ObjectId(session['user_id'])}))
    devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id'])}))
    
    # Convert devices to dict for easy access
    devices_dict = {str(device['_id']): device for device in devices}
    
    return render_template('schedule/schedules.html', schedules=schedules_list, devices=devices_dict)

@app.route('/schedule/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id']), 'type': 'actuator'}))
    
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        action = request.form.get('action')
        time = request.form.get('time')
        days = request.form.getlist('days')
        condition_type = request.form.get('condition_type')
        condition_value = request.form.get('condition_value')
        
        mongo.db.schedules.insert_one({
            'user_id': ObjectId(session['user_id']),
            'device_id': ObjectId(device_id),
            'action': action,
            'time': time,
            'days': days,
            'condition_type': condition_type,
            'condition_value': condition_value,
            'enabled': True,
            'created_at': datetime.utcnow()
        })
        
        flash('Jadwal berhasil ditambahkan!', 'success')
        return redirect(url_for('schedules'))
    
    return render_template('schedule/add_schedule.html', devices=devices)

@app.route('/schedule/<schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_schedule(schedule_id):
    schedule = mongo.db.schedules.find_one({'_id': ObjectId(schedule_id), 'user_id': ObjectId(session['user_id'])})
    if not schedule:
        flash('Jadwal tidak ditemukan!', 'danger')
        return redirect(url_for('schedules'))
    
    devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id']), 'type': 'actuator'}))
    
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        action = request.form.get('action')
        time = request.form.get('time')
        days = request.form.getlist('days')
        condition_type = request.form.get('condition_type')
        condition_value = request.form.get('condition_value')
        enabled = request.form.get('enabled') == 'on'
        
        mongo.db.schedules.update_one(
            {'_id': ObjectId(schedule_id)},
            {'$set': {
                'device_id': ObjectId(device_id),
                'action': action,
                'time': time,
                'days': days,
                'condition_type': condition_type,
                'condition_value': condition_value,
                'enabled': enabled
            }}
        )
        
        flash('Jadwal berhasil diperbarui!', 'success')
        return redirect(url_for('schedules'))
    
    return render_template('schedule/edit_schedule.html', schedule=schedule, devices=devices)

@app.route('/schedule/<schedule_id>/delete')
@login_required
def delete_schedule(schedule_id):
    schedule = mongo.db.schedules.find_one({'_id': ObjectId(schedule_id), 'user_id': ObjectId(session['user_id'])})
    if not schedule:
        flash('Jadwal tidak ditemukan!', 'danger')
        return redirect(url_for('schedules'))
    
    mongo.db.schedules.delete_one({'_id': ObjectId(schedule_id)})
    flash('Jadwal berhasil dihapus!', 'success')
    return redirect(url_for('schedules'))

@app.route('/schedule/<schedule_id>/toggle')
@login_required
def toggle_schedule(schedule_id):
    schedule = mongo.db.schedules.find_one({'_id': ObjectId(schedule_id), 'user_id': ObjectId(session['user_id'])})
    if not schedule:
        flash('Jadwal tidak ditemukan!', 'danger')
        return redirect(url_for('schedules'))
    
    new_status = not schedule.get('enabled', False)
    mongo.db.schedules.update_one(
        {'_id': ObjectId(schedule_id)},
        {'$set': {'enabled': new_status}}
    )
    
    status_text = 'diaktifkan' if new_status else 'dinonaktifkan'
    flash(f'Jadwal {status_text}!', 'success')
    return redirect(url_for('schedules'))

# History routes
@app.route('/history')
@login_required
def history():
    # Get last 50 history records
    history_list = list(mongo.db.sensor_data.find({'user_id': ObjectId(session['user_id'])})
                                 .sort('timestamp', -1)
                                 .limit(50))
    
    devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id'])}))
    devices_dict = {str(device['_id']): device for device in devices}
    
    return render_template('history/history.html', history=history_list, devices=devices_dict)

@app.route('/history/daily')
@login_required
def daily_history():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d')
    next_date = selected_date + timedelta(days=1)
    
    # Get history for selected date
    history_list = list(mongo.db.sensor_data.find({
        'user_id': ObjectId(session['user_id']),
        'timestamp': {
            '$gte': selected_date,
            '$lt': next_date
        }
    }).sort('timestamp', -1))
    
    devices = list(mongo.db.devices.find({'user_id': ObjectId(session['user_id'])}))
    devices_dict = {str(device['_id']): device for device in devices}
    
    return render_template('history/daily_history.html', history=history_list, devices=devices_dict, selected_date=selected_date)

# API endpoint for sensor data
@app.route('/api/sensor_data', methods=['POST'])
def receive_sensor_data():
    try:
        data = request.json
        device_id = data.get('device_id')
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        moisture = data.get('moisture')
        
        # Check if device exists and get user_id
        device = mongo.db.devices.find_one({'_id': ObjectId(device_id)})
        if not device:
            return jsonify({'success': False, 'message': 'Device not found'}), 404
        
        # Save sensor data
        mongo.db.sensor_data.insert_one({
            'user_id': device['user_id'],
            'device_id': ObjectId(device_id),
            'temperature': temperature,
            'humidity': humidity,
            'moisture': moisture,
            'timestamp': datetime.utcnow()
        })
        
        # Check if any schedules need to be triggered based on conditions
        schedules = list(mongo.db.schedules.find({
            'device_id': ObjectId(device_id),
            'enabled': True,
            'condition_type': {'$ne': None}
        }))
        
        for schedule in schedules:
            condition_type = schedule.get('condition_type')
            condition_value = float(schedule.get('condition_value', 0))
            action = schedule.get('action')
            
            trigger = False
            if condition_type == 'temperature' and temperature is not None:
                trigger = temperature >= condition_value
            elif condition_type == 'humidity' and humidity is not None:
                trigger = humidity <= condition_value
            elif condition_type == 'moisture' and moisture is not None:
                trigger = moisture <= condition_value
            
            if trigger:
                # Send command to RabbitMQ
                credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
                parameters = pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    virtual_host=RABBITMQ_VHOST,
                    credentials=credentials
                )
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                
                message = {
                    'device_id': device_id,
                    'command': action,
                    'timestamp': datetime.utcnow().isoformat(),
                    'triggered_by': 'condition',
                    'condition_type': condition_type,
                    'condition_value': condition_value,
                    'current_value': temperature if condition_type == 'temperature' else (
                        humidity if condition_type == 'humidity' else moisture
                    )
                }
                
                channel.basic_publish(
                    exchange='',
                    routing_key=device['topic'],
                    body=json.dumps(message)
                )
                
                connection.close()
                
                # Update device status in database
                mongo.db.devices.update_one(
                    {'_id': ObjectId(device_id)},
                    {'$set': {'status': action}}
                )
                
                # Log the triggered action
                mongo.db.triggered_actions.insert_one({
                    'user_id': device['user_id'],
                    'device_id': ObjectId(device_id),
                    'schedule_id': schedule['_id'],
                    'action': action,
                    'condition_type': condition_type,
                    'condition_value': condition_value,
                    'current_value': temperature if condition_type == 'temperature' else (
                        humidity if condition_type == 'humidity' else moisture
                    ),
                    'timestamp': datetime.utcnow()
                })
        
        return jsonify({'success': True, 'message': 'Data received successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Letakkan ini di bagian # Profile routes

@app.route('/api/user/stats')
@login_required
def user_stats():
    try:
        user_id = ObjectId(session['user_id'])

        # Hitung jumlah lahan (farms) milik pengguna
        farm_count = mongo.db.farms.count_documents({'user_id': user_id})

        # Hitung jumlah perangkat (devices) milik pengguna
        device_count = mongo.db.devices.count_documents({'user_id': user_id})

        # Kirim data sebagai JSON
        return jsonify({
            'success': True,
            'stats': {
                'farm_count': farm_count,
                'device_count': device_count
            }
        })

    except Exception as e:
        # Kirim pesan error jika terjadi masalah
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True,port=5604)