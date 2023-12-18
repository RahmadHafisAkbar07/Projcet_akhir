from pymongo import MongoClient
import jwt
import datetime
import hashlib
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import traceback
import os
from flask import send_from_directory
from werkzeug.utils import secure_filename
from bson import ObjectId
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)
app.config["TEMPLATES_AUTO_RELOAD"] = True


MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME =  os.environ.get("DB_NAME")
SECRET_KEY = os.environ.get("SECRET_KEY")
TOKEN_KEY = os.environ.get("TOKEN_KEY")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

UPLOAD_FOLDER = './static/hotel_pics/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

TOKEN_KEY = "mytoken"

import logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def home():
    try:
        token_receive = request.cookies.get("mytoken")
        user_info = None

        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        if user_info:
            if user_info['role'] == 'admin':
                return render_template('index.html', user_info=user_info)
            else:
                return render_template('index.html', user_info=user_info)
        else:
            # Handle cases where the user is not logged in
            return render_template('index.html')

    except jwt.ExpiredSignatureError:
        app.logger.error("JWT ExpiredSignatureError")
        return render_template("index.html")

    except jwt.exceptions.DecodeError:
        app.logger.error("JWT DecodeError")
        return render_template("index.html")


    
@app.route("/login")
def login():
    token_receive = request.cookies.get("mytoken")
    try:
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})
            if user_info:
                return redirect(url_for('home'))
            
        return render_template("login.html")
    
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template("login.html")
    

@app.route("/user_signup", methods=["POST"])
def user_signup():
    try:
        username_receive = request.form["username"]
        email_receive = request.form["email"]
        pw_receive = request.form["password"]
        pw_hash = hashlib.sha256(pw_receive.encode("utf-8")).hexdigest()

        user_exists = bool(db.users.find_one({"username": username_receive}))
        if user_exists:
            return jsonify({"result": "error_uname", "msg": f"An account with username {username_receive} already exists. Please Login!"})
        else:
            doc = {
                "username": username_receive,
                "email": email_receive,
                "password": pw_hash,
                "profile_info": "",
                "role": "member"
            }
            db.users.insert_one(doc)
            app.logger.info(f"User {username_receive} successfully signed up.")
            return jsonify({"result": "success"})

    except Exception as e:
        app.logger.error(f"Error during user signup: {str(e)}")
        return jsonify({"result": "error_server", "msg": "Internal server error. Please try again."})    

@app.route('/submit_booking', methods=['POST'])
def submit_booking():
    try:
        token_receive = request.cookies.get("mytoken")
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({'username': payload['id']})

        data = request.json
        name = data.get("name", "")
        contact = data.get("contact", "")
        nights = int(data.get("nights", 0))
        title = data.get("title", "")
        location = data.get("location", "")
        price = float(data.get("price", 0))
        username = user_info['username']
        
        

        total_price = nights * price

        booking_data = {
            "name": name,
            "contact": contact,
            "nights": nights,
            "title": title,
            "location": location,
            "price": price,
            "total_price": total_price,
            "username": username,
            "status": "pending",
            
            
        }
        db.bookings.insert_one(booking_data)

        return jsonify({"message": "Booking berhasil"})

    except Exception as e:
        app.logger.error(f"Error saat melakukan pemesanan: {str(e)}")
        traceback.print_exc()
        return jsonify({"message": f"Pemesanan gagal. Silakan coba lagi. Error: {str(e)}"}), 500
    

@app.route('/update_status', methods=['POST'])
def update_status():
    try:
        data = request.get_json()

        # Periksa apakah 'id_booking' dan 'status' ada dalam data JSON
        if 'id_booking' not in data or 'status' not in data:
            return jsonify({"error": "Data tidak lengkap"}), 400

        booking_id = ObjectId(data['id_booking'])
        new_status = data['status']

        # Perbarui status di basis data
        result = db.bookings.update_one(
            {'_id': booking_id},
            {'$set': {'status': new_status}}
        )

        if result.modified_count == 1:
            return jsonify({"message": "Status berhasil diperbarui"})
        else:
            return jsonify({"error": "Gagal memperbarui status"}), 500

    except Exception as e:
        app.logger.error(f"Error updating status: {str(e)}")
        return jsonify({"error": f"Gagal memperbarui status. Error: {str(e)}"}), 500



@app.route('/delete_booking', methods=['POST'])
def delete_booking():
    token_receive = request.cookies.get("mytoken")

    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )

        data = request.get_json()

        id_booking = ObjectId(data.get('id_booking'))
        title_hotel = data.get("title_hotel")

        db.bookings.delete_one({'_id': id_booking})

        return jsonify({'result': 'success', 'msg': 'Data booking berhasil dihapus'})

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({'result': 'error', 'msg': 'Token tidak valid'}), 401
    
@app.route('/cetak', methods=['GET'])
def cetak():
    try:
        token_receive = request.cookies.get("mytoken")
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        username = payload['id']
        user_info = db.users.find_one({'username': username})
        if not user_info:
            return jsonify({"error": "Pengguna tidak ditemukan"}), 404
        role = user_info.get("role")
        if role == "admin":
            bookings = db.bookings.find()
        else:
            bookings = db.bookings.find({'username': username})

        booking_list = []
        for booking in bookings:
            booking_data = {
                "_id": str(booking.get("_id")),
                "title": booking.get("title", ""),
                "price": booking.get("price", 0),
                "location": booking.get("location", ""),
                "name": booking.get("name", ""),
                "contact": booking.get("contact", ""),
                "nights": booking.get("nights", 0),
                "total_price": booking.get("total_price", 0),
                "status": booking.get("status", ""), 
            }
            booking_list.append(booking_data)

        return jsonify(bookings=booking_list)

    except Exception as e:
        app.logger.error(f"Error saat mengambil data pemesanan: {str(e)}")
        return jsonify({"error": f"Gagal mengambil pemesanan. Error: {str(e)}"}), 500
    



    
@app.route("/sign_in", methods=["POST"])
def sign_in():
    email_receive = request.form["email_give"]
    password_receive = request.form["password_give"]
    pw_hash = hashlib.sha256(password_receive.encode("utf-8")).hexdigest()
    result = db.users.find_one(
        {
            "email": email_receive,
            "password": pw_hash,
        }
    )
    if result:
        payload = {
            "id": result["username"],
            "exp": datetime.utcnow() + timedelta(seconds=60 * 60 * 24),
            "role": result["role"],
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        response = jsonify(
            {
                "result": "success",
                "token": token,
            }
        )
        response.set_cookie("mytoken", token, httponly=True)
        return response
    else:
        return jsonify(
            {
                "result": "fail",
                "msg": "We couldn't find a user with that username/password combination.",
            }
        )


@app.route('/discover_page')
def discover():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('discover.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("discover.html")

    except jwt.exceptions.DecodeError:
        return render_template("discover.html")

@app.route('/admin_dashboard')
def admin_dashboard():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('admin_dashboard.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("admin_dashboard.html")

    except jwt.exceptions.DecodeError:
        return render_template("admin_dashboard.html")

@app.route('/detail_page')
def detail_page():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('detail_page.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("detail_page.html")

    except jwt.exceptions.DecodeError:
        return render_template("detail_page.html")

    

@app.route('/tambah_hotel', methods=["POST"])
def tambah_hotel():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])

        name_receive = request.form.get('name_give')
        harga_receive = request.form.get('harga_give')
        location_receive = request.form.get('location_give')

        if 'file_give' in request.files:
            file = request.files.get('file_give')
            file_name = secure_filename(file.filename)
            picture_name = file_name  # Nama gambarnya hanya menggunakan nama file yang diupload
            file_path = f'./static/hotel_pics/{picture_name}'
            file.save(file_path)
        else:
            picture_name = 'default.jpg'

        doc = {
            'nama_hotel': name_receive,
            'harga_hotel': harga_receive,
            'location_hotel': location_receive,
            'gambar_hotel': picture_name,
        }

        # Masukkan data ke dalam basis data
        db.hotel.insert_one(doc)

        return jsonify({"result": "success", "msg": "Hotel berhasil ditambahkan"})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError) as e:
        print(f"Error: {e}")
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"result": "error", "msg": "Kesalahan Server Internal"})

@app.route('/delete_hotel', methods=['POST'])
def delete_hotel():
    token_receive = request.cookies.get("mytoken")

    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )

        data = request.get_json()

        id_hotel = ObjectId(data.get('id_hotel'))

        db.hotel.delete_one({'_id': id_hotel})

        return jsonify({'result': 'success', 'msg': 'Data hotel berhasil dihapus'})

    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({'result': 'error', 'msg': 'Token tidak valid'}), 401




 
@app.route('/get_hotel_data', methods=['GET'])
def get_hotel_data():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        # Ambil data hotel dari basis data
        hotels_cursor = db.hotel.find()

        # Ubah data cursor menjadi list
        hotel_list = []
        for hotel in hotels_cursor:
            hotel_data = {
                 "_id": str(hotel.get("_id")),
                "name": hotel.get("nama_hotel", ""),  # Sesuaikan dengan nama kolom di MongoDB
                "price": hotel.get("harga_hotel", 0),
                "location": hotel.get("location_hotel", ""),
                "image_url": hotel.get("gambar_hotel", "default.jpg")  # Ambil nama gambar dari dokumen
            }
            hotel_list.append(hotel_data)

        return jsonify(hotels={"hotels": hotel_list})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Gagal mengambil data hotel"}), 500
    

@app.route('/tambah')
def tambah():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('tambah.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("tambah.html")

    except jwt.exceptions.DecodeError:
        return render_template("tambah.html")
    
@app.route('/edit')
def edit():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('edit.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("edit.html")

    except jwt.exceptions.DecodeError:
        return render_template("edit.html")








@app.route('/daftar')
def daftar():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('daftar.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("daftar.html")

    except jwt.exceptions.DecodeError:
        return render_template("daftar.html")

@app.route('/orderstatus')
def order_status():
    token_receive = request.cookies.get("mytoken")
    try:
        user_info = None
        if token_receive:
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
            user_info = db.users.find_one({'username': payload['id']})

        return render_template('orderstatus.html', user_info=user_info)

    except jwt.ExpiredSignatureError:
        return render_template("orderstatus.html")

    except jwt.exceptions.DecodeError:
        return render_template("orderstatus.html")
    

@app.route('/logout')
def logout():
    response = redirect(url_for('login'))
    response.delete_cookie('mytoken', path='/')
    return response




    



if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)