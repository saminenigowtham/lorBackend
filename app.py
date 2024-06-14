from flask import Flask, request, jsonify,session,send_file
from pymongo import MongoClient
from flask_cors import CORS
from bson import ObjectId
import base64
import json
import pyotp
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_mail import Mail
from gridfs import GridFS
from apscheduler.schedulers.background import BackgroundScheduler


# Initialize Flask app
app = Flask(__name__)
CORS(app)
# Connect to MongoDB
client = MongoClient("mongodb+srv://gouthamsamineni:goutham07@cluster0.qq257ti.mongodb.net/?retryWrites=true&w=majority")
db = client['LOR']
collection = db['Student_Details']
users_collection = db['signUp_details']
staff_collection =db['staff_details']
yearFilter = db['yearfilter']
grid_fs = GridFS(db, collection='upload')
student_grid_fs = GridFS(db,collection='Student_Doc')
dean_grid_fs = GridFS(db,collection='Dean_Doc')
# Set a secret key for the Flask application
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

app.config['JWT_SECRET_KEY'] = '_5#y2L"F4Q8z\n\xec]/'  # Change this to a random secret key
jwt = JWTManager(app)


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
            expiration = datetime.utcnow() + timedelta(seconds=250)  # Define expiration here
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
            expiration = datetime.utcnow() + timedelta(seconds=600)  # Define expiration here
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
    print("application received")
    current_user = get_jwt_identity()
    print(current_user)
    form_data = request.form.to_dict()
    # print(form_data)
    try:
        username = current_user['username']
        registerNo = current_user['registerNo']
        
        # Check if the application form has already been submitted
        existing_application = collection.find_one({'registerNumber': registerNo})
        if existing_application:
            return jsonify({'error': 'Application already submitted'}), 400

        # Fetch the user's email
        email_fetch = users_collection.find_one({'registerNumber': registerNo})

        

        # Find all records in GridFS for the given student ID
        file_records = student_grid_fs.find({'student_id': registerNo})

        # Create a dictionary to store the named file IDs
        file_ids_dict = {}

        # Assign specific names to the file IDs (file_id1, file_id2, file_id3, etc.)
        for index, record in enumerate(file_records, start=1):
            # Create the key name based on the index (file_id1, file_id2, etc.)
            key_name = f"file_id{index}"
            file_ids_dict[key_name] = str(record._id)  # Convert ObjectId to string

        # Add the named file IDs to the form data
        form_data.update(file_ids_dict)

        # Insert the form data into the MongoDB collection
        collection.insert_one(form_data)
            

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
            <p class="content">We are pleased to inform you that the application submitted by the student <b>{student_name}</b> with register number <b>{registerNo}</b> has been <b>approved</b>.</p>
            <p class="content">The application was applied successfully and has met all the necessary criteria.</p>
            <p class="content">Thank you for your attention and cooperation.</p>
            <p class="signature">Best regards ,Sathyabama Institute of Science and Technology</p>
        </div>
    </body>
</html>

        """
        print(student_email_submit)
        send_email(subject_student_submit, body_student_submit, student_email_submit)

        # Getting names and emails of the selected staff members
        staff_names_submit = [form_data.get('prof1'), form_data.get('prof2'), form_data.get('prof3')]
        staff_emails_submit = set()  # Using a set to ensure uniqueness

        # Query the staff_details collection for the emails of the selected staff members
        for staff_name_submit in staff_names_submit:
            staff_details_submit = staff_collection.find_one({'name': staff_name_submit})
            if staff_details_submit:
                staff_emails_submit.add(staff_details_submit.get('email'))

        # Customized email design for staff
        subject_staff_submit = "Application Submit Notification (Staff)"
        student_name = form_data.get('name')
        student_reg = form_data.get('registerNumber')

        # Construct the email body for staff
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
                    <p class="content">We are pleased to inform you that the application of the student <b>{student_name}</b> with register number <b>{student_reg}</b> has been <b>approved</b>.</p>
                    <p class="content">Thank you for your attention and cooperation.</p>
                    <p class="signature">Best regards,<br>Sathyabama Institute of Science and Technology</p>
                </div>
            </body>
        </html>
        """

        # Send email notifications to staff members
        for staff_email in staff_emails_submit:
            print(staff_email)
            send_email(subject_staff_submit, body_staff_submit, staff_email)
        
        return jsonify({'message': 'Application received successfully'}), 200

    except Exception as e:
        # Handle any unexpected errors
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
    result = collection.delete_one({'registerNumber': register_number})
    return jsonify({'message': 'Application deleted successfully'}), 200
    if result.deleted_count == 1:
        return jsonify({'message': 'Application deleted successfully'}), 200
    else:
        return jsonify({'error': 'Application not found'}), 404
    return jsonify({'success': 'Application deleted successfully'})


    # register_number = data.get('register_Number')


#documentation uploading
@app.route('/student/upload', methods=['POST'])
def student_upload_file_gridfs():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        # Retrieve student ID from the request
        student_id = request.form.get('studentId')
        # Save the file to MongoDB GridFS
        file_id = student_grid_fs.put(file, filename=file.filename,student_id=student_id)
        # Retrieve the count value from the request
        count = request.form.get('count')
        print(count)
        print(student_id)
        # Insert the file ID into the appropriate collection based on the count value
        # if count == '1':
        #     collection.update_one({'registerNumber': student_id}, {'$set': {'file_id1': str(file_id)}})
        #     print("uploaded done")
        # elif count == '2':
        #     collection.update_one({'registerNumber': student_id}, {'$set': {'file_id2': str(file_id)}})
        #     print("uploaded done")
        # elif count == '3':
        #     collection.update_one({'registerNumber': student_id}, {'$set': {'file_id3': str(file_id)}})
        #     print("uploaded done")
        # else:
        #     return jsonify({'error': 'Invalid count value'})
        return jsonify({'success': True, 'file_id': str(file_id)})
    except Exception as e:
        return jsonify({'error': str(e)})
    
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

@app.route('/delete_gridfs_document', methods=['POST'])
def delete_gridfs_document():
    try:
        register_number = request.json.get('registerNumber')

        print("Received registerNumber to delete:", register_number)
        register_number = str(register_number)
        # Find the file record based on the register number
        # file_record = student_grid_fs.find_one({'student_id': register_number})

        file_records = student_grid_fs.find({'student_id': register_number})

        print("Query result:", file_records)

        # Delete each file record from GridFS
        if file_records:
            for file_record in file_records:
                student_grid_fs.delete(file_record._id)
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        file = request.files['file']
        register_number = request.form['registerNumber']  # Get the register number from the request form data
        # Calculate the expiry date (one month from now)
        expiry_date = datetime.now() + timedelta(days=30)
        # Save the file to GridFS with expiry metadata
        file_id = dean_grid_fs.put(file, filename=file.filename, student_id=register_number, expiry=expiry_date)
        count = request.form.get('count')
        print(count)
        
        # Update the student's database with the file ID
        if count=='1':
            print("deanfile 1 ")
            collection.update_one({'registerNumber': register_number}, {'$set': {'DeanfileId1': str(file_id)}})
            print("updated deanfile1")
        elif count=='2':
            print("deanfile 2")
            collection.update_one({'registerNumber': register_number}, {'$set': {'DeanfileId2': str(file_id)}})
            print("updated deanfile2")
        elif count=='3':
            print("deanfile 3")
            collection.update_one({'registerNumber': register_number}, {'$set': {'DeanfileId3': str(file_id)}})
            print("updated deanfile3")
        else:
            return jsonify({'error': 'Invalid count value'})

        return jsonify({'message': 'File uploaded successfully', 'file_id': str(file_id)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


def delete_expired_files():
    current_date = datetime.now()
    expired_files = dean_grid_fs.find({'metadata.expiry': {'$lt': current_date}})

    for file in expired_files:
        dean_grid_fs.delete(file._id)
        print(f"Deleted expired file: {file.filename}")

# Configure and start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(delete_expired_files, 'interval', days=1)  # Run daily
scheduler.start()



# dean delete
@app.route('/dean/delete_document', methods=['POST'])
def delete_document():
    
    data = request.json
    file_id = data.get('fileId')
    student_id = data.get('student_id')
    print('student_id for deleting from dean:', student_id)
    print('front end data:', file_id)

    try:
        student_id = str(student_id)
        # Find the file record based on the student_id
        file_records = dean_grid_fs.find({'_id': student_id})

        print("Query result:", file_records)

        # Iterate over each file record
        for file_record in file_records:
            # Delete the file record from GridFS
            dean_grid_fs.delete(file_record._id)
        # Update the collection to unset DeanfileIds
        collection.update_many({'registerNumber': student_id}, {'$unset': {'DeanfileId1': "", 'DeanfileId2': "", 'DeanfileId3': ""}})
        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400

# staff uploading files
@app.route('/staff/upload', methods=['POST'])
def upload_file_gridfs():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})
        
        file = request.files['file']
        student_id = request.form.get('student_id')
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        
        # Save the file to MongoDB GridFS
        file_id = grid_fs.put(file, filename=file.filename,student_id=student_id)
        return jsonify({'success': True, 'file_id': str(file_id)})
    except Exception as e:
        return jsonify({'error': str(e)})
#Dean can see the documnents
@app.route('/staff/documents', methods=['GET'])
@jwt_required()
def get_uploaded_documents():
    try:
        # Retrieve all files from GridFS collection
        files = grid_fs.find()
        documents = []

        # Extract relevant information for each file
        for file in files:
            document = {
                'file_id': str(file._id),
                'filename': file.filename,
                'upload_date': file.upload_date,
                'content_type': file.content_type,
                'registerNumber': file.student_id,
                'length': file.length
            }
            documents.append(document)
        # print(documents)
        return jsonify({'documents': documents})
    except Exception as e:
        return jsonify({'error': str(e)})
# staff will download the document from student
@app.route('/documentButton/<file_id>', methods=['GET'])
def get_document_fromStudent(file_id):
    try:
        # Convert the file_id parameter to ObjectId
        file_id_object = ObjectId(file_id)

        # Find the document file in GridFS by its ID
        file = student_grid_fs.get(file_id_object)

        # Check if the file exists
        if file:
            # Specify the MIME type based on the file extension
            mimetype = 'application/octet-stream'  # Default MIME type
            if file.filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            elif file.filename.endswith('.docx'):
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            # Add more conditions for other file types if needed

            # Return the file to the client with the specified MIME type
            return send_file(file, as_attachment=True, mimetype=mimetype, download_name=file.filename)
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/staff/documents/<file_id>', methods=['GET'])
# @jwt_required()
def get_document(file_id):
    try:
        # Find the document file in GridFS by its ID
        file = grid_fs.get(ObjectId(file_id))

        # Check if the file exists
        if file:
            # Specify the MIME type based on the file extension
            mimetype = 'application/octet-stream'  # Default MIME type
            if file.filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            elif file.filename.endswith('.docx'):
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            # Add more conditions for other file types if needed

            # Return the file to the client with the specified MIME type
            return send_file(file, as_attachment=True, mimetype=mimetype, download_name=file.filename)
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# student will dowload the file which student uploaded 
@app.route('/studentUploadedDocument/<file_id>', methods=['GET'])
def document_uploaded_dowload(file_id):
    try:
        # Convert the file_id parameter to ObjectId
        file_id_object = ObjectId(file_id)

        # Find the document file in GridFS by its ID
        file = student_grid_fs.get(file_id_object)

        # Check if the file exists
        if file:
            # Specify the MIME type based on the file extension
            mimetype = 'application/octet-stream'  # Default MIME type
            if file.filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            elif file.filename.endswith('.docx'):
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            # Add more conditions for other file types if needed

            # Return the file to the client with the specified MIME type
            return send_file(file, as_attachment=True, mimetype=mimetype, download_name=file.filename)
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# student will dowload the file from dean 
@app.route('/studentdocumentButton/<file_id>', methods=['GET'])
def document_dowload_for_Student(file_id):
    try:
        # Convert the file_id parameter to ObjectId
        file_id_object = ObjectId(file_id)

        # Find the document file in GridFS by its ID
        file = dean_grid_fs.get(file_id_object)

        # Check if the file exists
        if file:
            # Specify the MIME type based on the file extension
            mimetype = 'application/octet-stream'  # Default MIME type
            if file.filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            elif file.filename.endswith('.docx'):
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            # Add more conditions for other file types if needed

            # Return the file to the client with the specified MIME type
            return send_file(file, as_attachment=True, mimetype=mimetype, download_name=file.filename)
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
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
    try:
        app.run(debug=True)
    finally:
        scheduler.shutdown(wait=False)