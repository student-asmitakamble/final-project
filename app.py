from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from werkzeug.security import check_password_hash 
from flask import session
from flask import Response
import csv
from io import StringIO


app = Flask(__name__)


def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='Rakshu@12345',
        database='lb'
    )
    return connection


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        if 'email' in request.form and 'password' in request.form:
            email = request.form['email']
            password = request.form['password']
            print(f"Attempting login with email: {email} and password: {password}")

            
            connection = get_db_connection()
            cursor = connection.cursor()

           
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            print(f"User found: {user}")

            if user and user[2] == password:  
                print("Login successful!")
                user_id = user[0] 
                return redirect(url_for('user_dashboard', user_id=user_id))
            else:
                print("Invalid login attempt.")
                return render_template('user_login.html', error='Invalid email or password.')
        else:
            return render_template('user_login.html', error='Email and password are required.')

    return render_template('user_login.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        print(f"Attempting login with email: {email} and password: {password}")

     
        connection = get_db_connection()
        cursor = connection.cursor()

       
        cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
        admin = cursor.fetchone()
        print(f"Admin found: {admin}") 

        if admin and admin[2] == password:
            print("Login successful!")
            return redirect(url_for('admin_dashboard'))
        else:
            print("Invalid login attempt.")
            return render_template('admin_login.html', error='Invalid email or password.')

    return render_template('admin_login.html')






@app.route('/user-dashboard')
def user_dashboard():
    user_id = request.args.get('user_id')

    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, title, author, available FROM books WHERE available > 0")
    books = cursor.fetchall()

    
    cursor.execute("""
        SELECT b.title, br.date_from, br.date_to, br.status
        FROM borrow_requests br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s
    """, (user_id,))
    borrow_history = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('user_dashboard.html', books=books, borrow_history=borrow_history, user_id=user_id)

@app.route('/borrow-book', methods=['POST'])
def borrow_book():
    user_id = request.form['user_id']
    book_id = request.form['book_id']
    date_from = request.form['date_from']
    date_to = request.form['date_to']

    connection = get_db_connection()
    cursor = connection.cursor()

    
    cursor.execute("SELECT available FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()

    if book and book[0] > 0:
        
        cursor.execute("""
            INSERT INTO borrow_requests (user_id, book_id, date_from, date_to, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (user_id, book_id, date_from, date_to))

        
        cursor.execute("UPDATE books SET available = available - 1 WHERE id = %s", (book_id,))

        connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for('user_dashboard', user_id=user_id))

@app.route('/admin-dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        
        # Check which button was clicked
        if 'approve' in request.form:
            cursor.execute("UPDATE borrow_requests SET status = 'Approved' WHERE id = %s", (request_id,))
        elif 'deny' in request.form:
            cursor.execute("UPDATE borrow_requests SET status = 'Denied' WHERE id = %s", (request_id,))

        connection.commit()

    # Fetch all borrow requests
    cursor.execute("""
        SELECT br.id, u.email, b.title, br.status
        FROM borrow_requests br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
    """)
    borrow_requests = cursor.fetchall()

    # Fetch users for the user history section
    cursor.execute("SELECT id, email FROM users")
    users = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('admin_dashboard.html', borrow_requests=borrow_requests, users=users)


@app.route('/user_history/<int:user_id>', methods=['GET'])
def user_history(user_id):
    try:
        # Establish a database connection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Query to fetch user borrowing history with status = "approved"
        query = """
        SELECT 
            br.id, br.book_id, b.title AS book_name, br.date_from, br.date_to, br.status
        FROM 
            borrow_requests br
        JOIN 
            books b ON br.book_id = b.id
        WHERE 
            br.user_id = %s AND br.status = 'approved'
        """
        cursor.execute(query, (user_id,))
        borrowing_history = cursor.fetchall()

        # Close the connection
        cursor.close()
        connection.close()

        # Render the user history template with data
        return render_template('user_history.html', borrowing_history=borrowing_history)

    except mysql.connector.Error as err:
        return f"Error: {err}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

@app.route('/logout')
def logout():
    # Logic to handle logout (e.g., clearing session data)
   
    return redirect(url_for('home'))




@app.route('/download-history/<int:user_id>', methods=['GET'])
def download_history(user_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Fetch borrow history for the given user
    cursor.execute("""
        SELECT b.title, br.date_from, br.date_to, br.status
        FROM borrow_requests br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = %s
    """, (user_id,))
    borrow_history = cursor.fetchall()

    cursor.close()
    connection.close()

    # Create a CSV file in memory
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Book Title', 'From', 'To', 'Status'])  # Header row
    writer.writerows(borrow_history)  # Write data rows

    # Generate the response as a CSV file
    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=borrow_history_user_{user_id}.csv"}
    )


if __name__ == '__main__':
    app.run(debug=True)