import os
import bcrypt
from flask import Flask, request, jsonify, send_from_directory, render_template

# Make sure to import SQLAlchemy from flask_sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__, static_folder='public', template_folder='public')
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@host:port/dbname')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# We'll use a local 'uploads' folder for now. On a real server, you'd use a service like S3.
app.config['UPLOAD_FOLDER'] = 'uploads'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# Definiramo model za uporabniško tabelo v bazi
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')

# Nov model za restavracije
class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.String(10), nullable=False)
    tags = db.Column(db.String(255), nullable=True)
    distance = db.Column(db.String(20), nullable=True)
    rating = db.Column(db.Float, nullable=True)
    owner_username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=True)

# Nov model za predlagane posodobitve cen
class PriceUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_name = db.Column(db.String(255), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    old_price = db.Column(db.Float, nullable=True)
    new_price = db.Column(db.Float, nullable=False)
    submitted_by_username = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='pending')
    image_path = db.Column(db.String(255), nullable=True)

# Nov model za zahtevke za prevzem restavracije
class ClaimRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_name = db.Column(db.String(255), nullable=False)
    contact_name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    message = db.Column(db.Text, nullable=True)
    submitted_by_username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    proof_image_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')

# Root route to serve the main index.html file
@app.route('/')
def serve_index():
    return render_template('index.html')

# API endpoint za registracijo
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Manjkajoči podatki'}), 400
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        if not username or not email or not password:
            return jsonify({'message': 'Manjkajoči podatki'}), 400
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            return jsonify({'message': 'Uporabniško ime ali e-pošta že obstajata'}), 409
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(username=username, email=email, password_hash=hashed_password, role='user') 
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Uporabnik uspešno registriran'}), 201
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API endpoint za prijavo
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Manjkajoči podatki'}), 400
        identifier = data.get('identifier')
        password = data.get('password')
        if not identifier or not password:
            return jsonify({'message': 'Manjkajoči podatki'}), 400
        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash):
            return jsonify({'message': 'Prijava uspešna', 'username': user.username, 'role': user.role}), 200
        else:
            return jsonify({'message': 'Neveljavno uporabniško ime/e-pošta ali geslo'}), 401
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API za dodelitev vloge administratorja
@app.route('/api/make-admin', methods=['POST'])
def make_admin():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Manjkajoči podatki'}), 400
        username = data.get('username')
        user = User.query.filter_by(username=username).first()
        if user:
            user.role = 'admin'
            db.session.commit()
            return jsonify({'message': f'Uporabnik {username} je zdaj administrator.'}), 200
        return jsonify({'message': 'Uporabnik ni najden.'}), 404
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API pot za oddajo posodobitve cene
@app.route('/api/updates/submit', methods=['POST'])
def submit_update():
    try:
        data = request.form
        restaurant_name = data.get('restaurant_name')
        item_name = data.get('item_name')
        new_price = data.get('new_price')
        submitted_by = data.get('submitted_by')
        photo = request.files.get('photo')
        if not restaurant_name or not item_name or not new_price or not submitted_by or not photo:
            return jsonify({'message': 'Manjkajoči podatki za posodobitev'}), 400
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        image_filename = f"{restaurant_name}_{item_name}_{os.urandom(8).hex()}.jpg"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        photo.save(image_path)
        new_update = PriceUpdate(
            restaurant_name=restaurant_name,
            item_name=item_name,
            new_price=new_price,
            submitted_by_username=submitted_by,
            status='pending',
            image_path=image_path
        )
        db.session.add(new_update)
        db.session.commit()
        return jsonify({'message': 'Predlog posodobitve uspešno oddan!'}), 201
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API pot za pridobitev vseh čakajočih posodobitev (samo za administrativne vloge)
@app.route('/api/updates/pending', methods=['GET'])
def get_pending_updates():
    try:
        updates = PriceUpdate.query.filter_by(status='pending').all()
        updates_list = [{
            'id': update.id,
            'restaurant_name': update.restaurant_name,
            'item_name': update.item_name,
            'new_price': update.new_price,
            'submitted_by': update.submitted_by_username,
            'image_path': update.image_path
        } for update in updates]
        return jsonify(updates_list), 200
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API pot za oddajo zahtevka za prevzem restavracije
@app.route('/api/claim/submit', methods=['POST'])
def submit_claim():
    try:
        data = request.form
        restaurant_name = data.get('restaurantName')
        contact_name = data.get('contactName')
        contact_email = data.get('contactEmail')
        phone = data.get('phone')
        message = data.get('message')
        submitted_by_username = data.get('submitted_by_username')
        proof_image = request.files.get('proofImage')
        
        if not restaurant_name or not contact_name or not contact_email or not submitted_by_username or not proof_image:
            return jsonify({'message': 'Manjkajoči podatki za zahtevek'}), 400
        
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        
        proof_filename = f"claim_{restaurant_name}_{os.urandom(8).hex()}.jpg"
        proof_path = os.path.join(app.config['UPLOAD_FOLDER'], proof_filename)
        proof_image.save(proof_path)
        
        new_claim = ClaimRequest(
            restaurant_name=restaurant_name,
            contact_name=contact_name,
            contact_email=contact_email,
            phone=phone,
            message=message,
            submitted_by_username=submitted_by_username,
            proof_image_path=proof_path
        )
        db.session.add(new_claim)
        db.session.commit()
        
        return jsonify({'message': 'Zahtevek za prevzem uspešno oddan!'}), 201
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API pot za pridobitev čakajočih zahtevkov
@app.route('/api/claim/pending', methods=['GET'])
def get_pending_claims():
    try:
        claims = ClaimRequest.query.filter_by(status='pending').all()
        claims_list = [{
            'id': claim.id,
            'restaurant_name': claim.restaurant_name,
            'contact_name': claim.contact_name,
            'contact_email': claim.contact_email,
            'phone': claim.phone,
            'message': claim.message,
            'submitted_by': claim.submitted_by_username,
            'proof_image_path': claim.proof_image_path
        } for claim in claims]
        return jsonify(claims_list), 200
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# API pot za sprejemanje posodobitve cene
@app.route('/api/updates/approve/<int:update_id>', methods=['POST'])
def approve_update(update_id):
    try:
        update = PriceUpdate.query.get(update_id)
        if update:
            update.status = 'approved'
            db.session.commit()
            return jsonify({'message': 'Posodobitev sprejeta!'}), 200
        return jsonify({'message': 'Posodobitev ni najdena.'}), 404
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# Nova pot za zavrnitev posodobitve
@app.route('/api/updates/reject/<int:update_id>', methods=['POST'])
def reject_update(update_id):
    try:
        update = PriceUpdate.query.get(update_id)
        if update:
            update.status = 'rejected'
            db.session.commit()
            return jsonify({'message': 'Posodobitev zavrnjena.'}), 200
        return jsonify({'message': 'Posodobitev ni najdena.'}), 404
    except Exception as e:
        return jsonify({'message': 'Notranja strežniška napaka'}), 500

# Pot za streženje naloženih slik
@app.route('/uploads/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=os.environ.get('PORT', 5000))
