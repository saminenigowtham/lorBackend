import os
from sched import scheduler
from flask import Flask, redirect, request, jsonify,session,send_file
from pymongo import MongoClient
from flask_cors import CORS, cross_origin
from bson import ObjectId
import base64
import json
import pyotp
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, verify_jwt_in_request
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_mail import Mail
from gridfs import GridFS
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename

import driveAPI


# Initialize Flask app
app = Flask(__name__)
CORS(app)
# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
# Connect to MongoDB
client = MongoClient(MONGO_URI)
# Set a secret key for the Flask application
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY") # Change this to a random secret key

FOLDER_ID = os.getenv("FOLDER_ID")
DEAN_FOLDER_ID = os.getenv("DEAN_FOLDER_ID")
STAFF_TO_DEAN_FOLDER_ID = os.getenv("STAFF_TO_DEAN_FOLDER_ID")

jwt = JWTManager(app)

db = client['LOR']
collection = db['Student_Details']
users_collection = db['signUp_details']
staff_collection =db['staff_details']
yearFilter = db['yearfilter']
uplods_to_dean = db['upload']
# grid_fs = GridFS(db, collection='upload')
student_grid_fs = GridFS(db,collection='Student_Doc')
# dean_grid_fs = GridFS(db,collection='Dean_Doc')


# Set the path for storing uploaded images
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

upload_dir = os.path.join(app.root_path, UPLOAD_FOLDER)
os.makedirs(upload_dir, exist_ok=True)

# Set up Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# drive code


# Register
@app.route('/register', methods=['POST'])
def register():
    data = request.form.to_dict()
    # print(data)
    try:
       
       
        username = data.get('username')
        email = data.get('email')

        if not username or not email:
            return jsonify({'error': 'Username or email missing in request.'}), 400

        # Check if the email is already registered
        user_exists = users_collection.find_one({'username': username})
        email_exists = users_collection.find_one({'email': email})
        if user_exists or email_exists:
            return jsonify({'message': 'User or email already exists.'}), 400

        # Hash the password
        # hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')

        # data['password'] = hashed_password
        # Insert new user into the database
        users_collection.insert_one(data)

        return jsonify({'message': 'User registered successfully'}), 201

    except Exception as e:
        return jsonify({'error': 'An error occurred while registering.'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    userType = data.get('userType', '')

    # Check if the username exists in the database
    user_data = users_collection.find_one({'username': username, 'userType': userType})

    if user_data:
        # Verify the password
        print("user found")
        if user_data['password'] == password:
            print("password was correct")
            registerNo = user_data['registerNumber']
            expiration = datetime.utcnow() + timedelta(seconds=2000)  # Define expiration here
            token_data = {
                'username': username,
                'registerNo': registerNo,
                'expiration': expiration.strftime("%Y-%m-%d %H:%M:%S")
            }
            token = create_access_token(identity=token_data)
            return jsonify({'token': token, 'success': True}), 200
        else:
            return jsonify({'sucess':False}),201
    # Invalid username or password
    return jsonify({'success': False}), 401
@app.route('/stafflogin', methods=['POST'])
def stafflogin():
    data = request.json
    email = data.get('email', '')
    password = data.get('password', '')
    userType = data.get('userType', '')

    # Check if the username exists in the database
    user_data = users_collection.find_one({'email': email, 'userType': userType})

    if user_data:
        # Verify the password
        print("user found")
        if user_data['password'] == password:
            print("password was correct")
            expiration = datetime.utcnow() + timedelta(seconds=2000)  # Define expiration here
            token_data = {
                'email': email,
                'expiration': expiration.strftime("%Y-%m-%d %H:%M:%S")
            }
            token_staff = create_access_token(identity=token_data)
            # print(token_staff)
            return jsonify({'token_staff': token_staff, 'success': True}), 200
        else:
            return jsonify({'sucess':False}),201
    # Invalid username or password
    return jsonify({'success': False}), 401

# checking mail's and sends otp
@app.route('/check-email-exists', methods=['POST'])
def check_email_and_generate_otp():
    email = request.json.get('email')
    if email:
        # Query MongoDB to check if the email exists
        user = users_collection.find_one({'email': email})
        if user:
            # Generate OTP
            totp = pyotp.TOTP(pyotp.random_base32(), interval=300)  # 5 minutes interval
            otp = totp.now()
            # print(otp)
            # Store OTP and expiration time in the database
            expiration_time = datetime.utcnow() + timedelta(minutes=5)
            users_collection.update_one({'email': email}, {'$set': {'otp': otp, 'otp_expiration_time': expiration_time}})
            subject_OTP = "Your One-Time Password (OTP)"
            body_OTP = f"Hello,\n\nYour One-Time Password (OTP) is: <h2>{otp}</h2>\n\nPlease use this OTP to complete your action.\n\nBest regards,\n<p>Best regards,<br>Sathyabama Institute of Science and Technology</p>"
            send_email(subject_OTP, body_OTP, email)
            return jsonify({'exists': True}), 200
    return jsonify({'exists': False}), 200

# verifying otp
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    email = request.json.get('email')
    otp = request.json.get('otp')
    if email and otp:
        # Query MongoDB to get the user record
        user = users_collection.find_one({'email': email})
        if user:
            stored_otp = user.get('otp')
            expiration_time = user.get('otp_expiration_time')
            if stored_otp and expiration_time and otp == stored_otp and datetime.utcnow() < expiration_time:
                # OTP is valid and within the time limit
                return jsonify({'verified': True}), 200
    return jsonify({'verified': False}), 200

@app.route('/update-password', methods=['POST'])
def password_update():
    # Extract data from JSON request
    email = request.json.get('email')
    new_password = request.json.get('newPassword')

    # Update password for the user with the specified email
    result = users_collection.update_one({'email': email}, {'$set': {'password': new_password}})

    if result.modified_count == 1:
        return jsonify({'message': 'Password updated successfully'})
    else:
        return jsonify({'message': 'Failed to update password'})

@app.route('/student/dashboard', methods=['POST'])
@jwt_required()
def receive_application():
    print("Application received")
    current_user = get_jwt_identity()
    print(current_user)
    form_data = request.form.to_dict()
    print(form_data)
    try:
        username = current_user['username']
        registerNo = current_user['registerNo']

        # Fetch the user's email
        email_fetch = users_collection.find_one({'registerNumber': registerNo})

        # Use upsert to insert or update the form data
        collection.update_one(
            {'registerNumber': registerNo},  # Query filter
            {'$set': form_data},            # Update or set new data
            upsert=True                     # Create a new document if none exists
        )

        # Send email to student
        student_email_submit = email_fetch.get('email')
        subject_student_submit = "Application was Applied Successfully (Student)"
        body_student_submit = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Hello {username},</p>
                    <p class="content">Your application has been successfully submitted/updated.</p>
                    <p class="content">Thank you for using our platform!</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """
        print(student_email_submit)
        send_email(subject_student_submit, body_student_submit, student_email_submit)

        # Notify staff
        staff_names_submit = [form_data.get('prof1'), form_data.get('prof2'), form_data.get('prof3')]
        staff_emails_submit = set()  # Avoid duplicate emails

        # Get staff emails
        for staff_name_submit in staff_names_submit:
            staff_details_submit = staff_collection.find_one({'name': staff_name_submit})
            if staff_details_submit:
                staff_emails_submit.add(staff_details_submit.get('email'))

        # Email template for staff
        subject_staff_submit = "Application Submit Notification (Staff)"
        student_name = form_data.get('name')
        student_reg = form_data.get('registerNumber')
        body_staff_submit = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Respected colleague,</p>
                    <p class="content">The application of the student <b>{student_name}</b> with register number <b>{student_reg}</b> has been submitted or updated.</p>
                    <p class="content">Thank you for your cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """

        # Send staff notifications
        for staff_email in staff_emails_submit:
            print(staff_email)
            send_email(subject_staff_submit, body_staff_submit, staff_email)

        return jsonify({'message': 'Application submitted/updated successfully'}), 200

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500



@app.route('/student/dashboard/getData', methods=['POST'])
@jwt_required()
def data_sender():
    current_user = get_jwt_identity()
    print(current_user)
    registerNo = current_user['registerNo']
    print(registerNo)
    data_available = collection.find_one({'registerNumber': registerNo})
    if data_available:
        data_available['_id'] = str(data_available['_id'])
        return jsonify(data_available), 200
    else:
        return jsonify({'error': 'Data not found'}), 404


@app.route('/student/dashboard/delete', methods=['DELETE'])  # Allow DELETE requests
def handle_student_dashboard_delete():
    data = request.json  # Assuming you send JSON data with the application fields
    # print(data)
    register_number = data.get('registerNumber')  # Corrected key access
    print('for the data to delete :',register_number)
    if not register_number:
        return jsonify({'error': 'Register Number not provided'}), 400
    
    # Perform deletion in MongoDB based on register number
    collection.delete_one({'registerNumber': register_number})
    return jsonify({'message': 'Application deleted successfully'}), 200

# documents uploading
@app.route('/student/upload', methods=['POST'])

def student_upload_file_to_drive():
    # FOLDER_ID = '11SCCKU5wyoQ30HgqSRz-5siWXBIvuCpM'
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Retrieve student ID and count from the request
        student_id = request.form.get('studentId')
        count = request.form.get('count')
        if not student_id or not count:
            return jsonify({'error': 'Missing studentId or count'}), 400

        # Save the file temporarily
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_file_path)
        shareable_link = driveAPI.upload_file_to_drive(temp_file_path, file.filename,FOLDER_ID)
        print(f'https://drive.google.com/file/d/{shareable_link}')
        formatted_link = f'https://drive.google.com/file/d/{shareable_link}'
        os.remove(temp_file_path)


        # Update or insert the record in MongoDB
        update_field = {f"file_id{count}": formatted_link}
        collection.update_one(
            {"registerNumber": student_id},
            {"$set": update_field},
            upsert=True
        )
        return jsonify({'success': True, 'shareable_link': shareable_link}), 200
    except Exception as e:
        print(f"Error: {str(e)}")  # Log the error message
        return jsonify({'error': str(e)}), 500

    


    
@app.route('/student/upload/get', methods=['GET'])
@jwt_required()
def get_file_data():  
    try:
        # Get the current user's register number from the JWT token
        current_user_register_number = get_jwt_identity().get('registerNo')
        current_user_register_number = str(current_user_register_number)
        
        # Query GridFS to find the file data based on the register number
        file_record = student_grid_fs.find_one({'student_id': current_user_register_number})
        if not file_record:
            return jsonify({'error': 'File data not found for the provided register number'}), 404
        
        # Return the filename and file ID
        return jsonify({
            'filename': file_record.filename,
            'file_id': str(file_record._id)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# @app.route('/delete_gridfs_document', methods=['POST'])
# def delete_gridfs_document():
#     try:
#         register_number = request.json.get('registerNumber')

#         print("Received registerNumber to delete:", register_number)
#         register_number = str(register_number)
#         # Find the file record based on the register number
#         # file_record = student_grid_fs.find_one({'student_id': register_number})

#         file_records = student_grid_fs.find({'student_id': register_number})

#         print("Query result:", file_records)

#         # Delete each file record from GridFS
#         if file_records:
#             for file_record in file_records:
#                 student_grid_fs.delete(file_record._id)
#             return jsonify({'success': True}), 200
#         else:
#             return jsonify({'error': 'File not found'}), 404
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


@app.route('/staff/dashboard', methods=['POST'])
@jwt_required()
def get_student_details():
    student_details = list(collection.find())
    # Convert ObjectId to string for JSON serialization
    for student in student_details:
        student['_id'] = str(student['_id'])
    print(student_details)
    return jsonify(student_details)

@app.route('/staff/studentCard',methods=['GET'])
@jwt_required()
def student_card():
    print("application received")
    current_user = get_jwt_identity()
    print(current_user)
    try: 
        print("details fetching....")
        student_details = list(collection.find())
        # Convert ObjectId to string for JSON serialization
        for student in student_details:
            student['_id'] = str(student['_id'])
        # print(student_details)
        return jsonify(student_details)
    except Exception as e:
        print("Error fetching student details:", e)
        return jsonify({"error": "An error occurred while fetching student details"}), 500
#Dean Visited
@app.route('/dean/visited', methods=['POST'])
def dean_visited():
    data = request.get_json()  # Parse the JSON data
    student_id = data.get('studentId')  # Extract the student ID from the request

    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400  # Validate input

    try:
        # Convert to ObjectID if required
        object_id = ObjectId(student_id) if not isinstance(student_id, ObjectId) else student_id

        # Correct update operation with ObjectID and proper data type
        result = collection.update_one({'_id': object_id}, {'$set': {'Visited': True}})

        if result.matched_count == 0:
            return jsonify({'error': 'Student not found'}), 404  # Handle case where no document is found

        return jsonify({'message': 'Visited status updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Return 500 for server errors
#Dean Upload
@app.route('/Dean/upload', methods=['POST'])
def dean_upload_file():
    try:
        # DeanFolderID = '12VH2_qO0HKlZungRpOm19QIzSu2GTPPL'
        
        # Ensure all required form data is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        if 'registerNumber' not in request.form or 'count' not in request.form:
            return jsonify({'error': 'Missing registerNumber or count in the form data'}), 400

        file = request.files['file']
        register_number = request.form['registerNumber']  # Get the register number from the form data
        count = request.form.get('count')

        if not file or file.filename == '':
            return jsonify({'error': 'No file selected for upload'}), 400

        # Save the file temporarily to the upload folder
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_file_path)

        # Upload the file to Google Drive and get the shareable link
        shareable_link = driveAPI.upload_file_to_drive(temp_file_path, file.filename, DEAN_FOLDER_ID)
        formatted_link = f'https://drive.google.com/file/d/{shareable_link}'
        print("Shareable Link:", formatted_link)

        # Remove the temp file after upload
        os.remove(temp_file_path)

        # Update the MongoDB record based on count
        update_field = f'DeanfileId{count}'
        if count in ['1', '2', '3']:
            collection.update_one({'registerNumber': register_number}, {'$set': {update_field: formatted_link}})
            print(f"Updated {update_field} for register number {register_number}")
        else:
            return jsonify({'error': 'Invalid count value'}), 400

        return jsonify({'message': 'File uploaded successfully', 'file_link': formatted_link}), 200

    except Exception as e:
        print("Error:", str(e))
        return jsonify({'error': str(e)}), 400



# def delete_expired_files():
#     current_date = datetime.now()
#     expired_files = dean_grid_fs.find({'metadata.expiry': {'$lt': current_date}})

#     for file in expired_files:
#         dean_grid_fs.delete(file._id)
#         print(f"Deleted expired file: {file.filename}")

# # Configure and start the scheduler
# scheduler = BackgroundScheduler()
# scheduler.add_job(delete_expired_files, 'interval', days=1)  # Run daily
# scheduler.start()



# dean delete
# @app.route('/dean/delete_document', methods=['POST'])
# def delete_document():
    
#     data = request.json
#     file_id = data.get('fileId')
#     student_id = data.get('student_id')
#     print('student_id for deleting from dean:', student_id)
#     print('front end data:', file_id)

#     try:
#         student_id = str(student_id)
#         # Find the file record based on the student_id
#         file_records = dean_grid_fs.find({'_id': student_id})

#         print("Query result:", file_records)

#         # Iterate over each file record
#         for file_record in file_records:
#             # Delete the file record from GridFS
#             dean_grid_fs.delete(file_record._id)
#             dean_grid_fs.chunks.delete_many({'files_id': file_record._id})
#         # Update the collection to unset DeanfileIds
#         collection.update_many({'registerNumber': student_id}, {'$unset': {'DeanfileId1': "", 'DeanfileId2': "", 'DeanfileId3': ""}})
#         return jsonify({'success': True}), 200

#     except Exception as e:
#         return jsonify({'error': str(e)}), 400

# staff uploading files
@app.route('/staff/upload', methods=['POST'])
def upload_file_gridfs():
    # staffToDean_FolderId = '118vzYmUzSJXYTewfwkxJ8-vPQmnK3lT9'
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})
        
        file = request.files['file']
        student_id = request.form.get('student_id')
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        
        # Generate the formatted filename
        filename = f"SIST-CSE-{student_id.upper()}-{file.filename.split('.')[0].upper()}.pdf"

        # Save the file temporarily
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(temp_file_path)

        # Upload the file to Google Drive
        shareable_link = driveAPI.upload_file_to_drive(temp_file_path, file.filename, STAFF_TO_DEAN_FOLDER_ID)
        formatted_link = f'https://drive.google.com/file/d/{shareable_link}'
        print(formatted_link)

        # Remove the temporary file
        os.remove(temp_file_path)

        # Insert the details into the MongoDB `uploads` collection
        uplods_to_dean.insert_one({
            'filename': filename,
            'student_id': student_id,
            'formatted_link': formatted_link
        })

        return jsonify({'success': True, 'file_id': formatted_link})
    except Exception as e:
        return jsonify({'error': str(e)})

#Dean can see the documnents
@app.route('/staff/documents', methods=['GET'])
@jwt_required()
def get_uploaded_documents():
    try:
        # Retrieve all files from GridFS collection
        files = uplods_to_dean.find()
        documents = []

        # Extract relevant information for each file
        for file in files:
            document = {
                'file_id': str(file['_id']),
                'filename': file['filename'],
                'registerNumber': file['student_id'],
                'formatted_link': file['formatted_link'] 
            }
            documents.append(document)
        # print(documents)
        return jsonify({'documents': documents})
    except Exception as e:
        return jsonify({'error': str(e)})
# staff will download the document from student
from flask import jsonify

from flask import redirect, jsonify

@app.route('/documentButton/<registerNumber>/<file_id>', methods=['GET'])
def get_document_link(registerNumber, file_id):
    try:
        # Find the document in the student collection using the register number
        student = collection.find_one({"registerNumber": registerNumber})

        if not student:
            return jsonify({'error': 'Student not found'}), 404

        # Fetch the file link from the collection using the provided file_id
        file_link = student.get(file_id)

        if not file_link:
            return jsonify({'error': 'File ID not found for the student'}), 404

        # Redirect to the file link
        return redirect(file_link)
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# @app.route('/staff/documents/<file_id>', methods=['GET'])
# # @jwt_required()
# def get_document(file_id):
#     try:
#         # Find the document file in GridFS by its ID
#         file = grid_fs.get(ObjectId(file_id))

#         # Check if the file exists
#         if file:
#             # Specify the MIME type based on the file extension
#             mimetype = 'application/octet-stream'  # Default MIME type
#             if file.filename.endswith('.pdf'):
#                 mimetype = 'application/pdf'
#             elif file.filename.endswith('.docx'):
#                 mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
#             # Add more conditions for other file types if needed

#             # Return the file to the client with the specified MIME type
#             return send_file(file, as_attachment=True, mimetype=mimetype, download_name=file.filename)
#         else:
#             return jsonify({'error': 'Document not found'}), 404
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


# student will dowload the file which student uploaded \
@jwt_required()
@app.route('/studentUploadedDocument/<file_id>', methods=['GET'])
def document_uploaded_download(file_id):
    print(file_id)
    try:
        verify_jwt_in_request()
        # Retrieve the current user's register number from the JWT identity
        current_user_register_number = get_jwt_identity().get('registerNo')
        current_user_register_number = str(current_user_register_number)

        # Find the student record using the register number
        student_record = collection.find_one({'registerNumber': current_user_register_number})
        print(f"Student Record: {student_record}")

        if not student_record:
            return jsonify({'error': 'Student record not found'}), 404

        # Extract the file link using the provided file_id
        file_link = student_record.get(file_id)
        print(f"File Link: {file_link}")

        if not file_link:
            return jsonify({'error': 'File link not found'}), 404

        # Return only the file URL, not wrapped in a JSON object
        print(file_link)
        return file_link, 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# student will dowload the file from dean 
@jwt_required()
@app.route('/studentdocumentButton/<file_id>', methods=['GET'])
def dean_uploaded_download(file_id):
    try:
        verify_jwt_in_request()

        current_user_register_number = str(get_jwt_identity().get('registerNo'))
        student_record = collection.find_one({'registerNumber': current_user_register_number})

        if not student_record:
            return jsonify({'error': 'Student record not found'}), 404

        # Fetch file link using the file_id key
        file_link = student_record.get(file_id)

        if not file_link:
            return jsonify({'error': 'File link not found'}), 404

        return file_link, 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# staff can see the approved students
@app.route('/staff/filterStudents/<year>', methods=['GET'])
# @jwt_required()
def details_of_students_approved(year):
    # Assuming yearFilter is some database collection
    student_details_year = list(yearFilter.find({'year_of_graduation': year}))
    
    # Convert ObjectId to string for JSON serialization
    for student in student_details_year:
        student['_id'] = str(student['_id'])

    return jsonify(student_details_year)

# respone yes or no 

responces = db['responce']
@app.route('/respond/<register_number>/<staff_id>', methods=['POST'])
def save_response(register_number, staff_id):
    try:
        data = request.json
        response = data.get('response')  # "Yes" or "No"
        reason = data.get('reason') if response == 'No' else None

        if response not in ['Yes', 'No']:
            return jsonify({'error': 'Valid response ("Yes" or "No") is required'}), 400

        # Update the database with the response and reason (if applicable)
        update_data = {'response': response}
        if reason:
            update_data['reason'] = reason

        result = responces.update_one(
            {'registerNumber': register_number, 'staffId': int(staff_id)},
            {'$set': update_data},
            upsert=True
        )

        # Check if a new document was inserted
        if result.matched_count == 0 and result.upserted_id:
            return jsonify({'message': 'New record created successfully', 'id': str(result.upserted_id)}), 201
        elif result.matched_count > 0:
            return jsonify({'message': 'Record updated successfully'}), 200
        else:
            return jsonify({'error': 'Unexpected error occurred'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# MAIL Part

@app.route('/students/<student_id>', methods=['PUT'])
def update_student_status(student_id):
    data = request.json
    new_status = data.get('status')

    # Get the student details
    student = collection.find_one({'_id': ObjectId(student_id)})
    print(student)
    
    # print(f"Student details: {student}")
    if new_status=="approved":
        if student:
            student_name = student.get('name')
            yearOfGraduation = student.get('yearofGraduation')
            register_number = student.get('registerNumber')
            appliedCountry = student.get('appliedCountry')
            # inserting data to mongodb for filter 
            student_data = {
                'student_name': student_name,
                'year_of_graduation': yearOfGraduation,
                'register_number': register_number,
                'applied_country': appliedCountry
            }
            yearFilter.insert_one(student_data)
            # Check if user document exists in the users_collection
            user_document = users_collection.find_one({'registerNumber': register_number})

            if user_document:
                student_email = user_document.get('email')

                # Update the status in the MongoDB collection
                collection.update_one(
                    {'_id': ObjectId(student_id)},
                    {'$set': {'status': new_status}}
                )

                # Get the names and emails of the selected staff members
                staff_names = [student.get('prof1'), student.get('prof2'), student.get('prof3')]
                staff_emails = []

                # Query the staff_details collection for the emails of the selected staff members
                for staff_name in staff_names:
                    staff_details = staff_collection.find_one({'name': staff_name})
                    if staff_details:
                        staff_emails.append(staff_details.get('email'))

                # Customized email design for staff
                subject_staff = "Application Approval Notification (Staff)"
                for staff_email, staff_name in zip(staff_emails, staff_names):
                    student_name = student.get('name')
                    student_reg = student.get('registerNumber')

                    # Customize the email body for staff
                    body_staff = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Respected {staff_name},</p>
                    <p class="content">We are pleased to inform you that the application of the student <b>{student_name}</b> with register number <b>{student_reg}</b> has been <b>approved</b>.</p>
                    <p class="content">Thank you for your attention and cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """
                    send_email(subject_staff, body_staff, staff_email)

                # Customized email design for student
                subject_student = "Application Approval Notification (Student)"
                body_student = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Hii, {student_name},</p>
                    <p class="content">We are pleased to inform you that your application has been <b>approved</b>.</p>
                    <p class="content">Thank you for your cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """
                send_email(subject_student, body_student, student_email)

                return jsonify({'success': True})
            else:
                return jsonify({'error': 'User document not found'}), 404
        else:
            return jsonify({'error': 'Student document not found'}), 404
    else:
        if student:
            register_number = student.get('registerNumber')

            # Check if user document exists in the users_collection
            user_document = users_collection.find_one({'registerNumber': register_number})

            if user_document:
                student_email = user_document.get('email')

                # Update the status in the MongoDB collection
                collection.update_one(
                    {'_id': ObjectId(student_id)},
                    {'$set': {'status': new_status}}
                )

                # Get the names and emails of the selected staff members
                staff_names = [student.get('prof1'), student.get('prof2'), student.get('prof3')]
                staff_emails = []

                # Query the staff_details collection for the emails of the selected staff members
                for staff_name in staff_names:
                    staff_details = staff_collection.find_one({'name': staff_name})
                    if staff_details:
                        staff_emails.append(staff_details.get('email'))

                # Customized email design for staff
                subject_staff = "Application Approval Notification (Staff)"
                for staff_email, staff_name in zip(staff_emails, staff_names):
                    student_name = student.get('name')
                    student_reg = student.get('registerNumber')

                    # Customize the email body for staff
                    body_staff = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Respected {staff_name},</p>
                    <p class="content">We are sorry to inform you that the application of the student <b>{student_name}</b> with register number <b>{student_reg}</b> has been <b>declined</b>.</p>
                    <p class="content">Thank you for your attention and cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """
                    send_email(subject_staff, body_staff, staff_email)

                # Customized email design for student
                subject_student = "Application Approval Notification (Student)"
                body_student = f"""
        <html>
            <head>
                <style>
                    .greeting {{
                        font-size: 18px;
                        font-weight: bold;
                        color: #333333;
                    }}
                    .content {{
                        font-size: 16px;
                        color: #555555;
                    }}
                    .signature {{
                        font-size: 16px;
                        color: #A10035;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <p class="greeting">Dear {student_name},</p>
                    <p class="content">We are sorry to inform you that your application has been <b>declined</b>.</p>
                    <p class="content">Thank you for your cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """
                send_email(subject_student, body_student, student_email)

                return jsonify({'success': True})
            else:
                return jsonify({'error': 'User document not found'}), 404
        else:
            return jsonify({'error': 'Student document not found'}), 404
def send_email(subject, body, to_email):
    sender_email = "sanjeevsaisasank9@gmail.com"  # Replace with your email
    app_password = "keko ekaf eyti hrrl"  # Replace with your app password

    try:
        if body and to_email:
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = to_email
            message["Subject"] = subject

            # Attach the HTML body
            message.attach(MIMEText(body, "html"))

            # Connect to Gmail's SMTP server
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender_email, app_password)

                # Send the email
                server.sendmail(sender_email, to_email, message.as_string())

            print("Email sent successfully!")
        else:
            print(f"Error sending email: Body: {body}, To: {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")
if __name__ == "__main__":
    # try:
    app.run(debug=True)
    # finally:
    #     scheduler.shutdown(wait=False)