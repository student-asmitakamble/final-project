from flask import Flask, render_template, request, redirect, url_for,Response
import mysql.connector
from werkzeug.security import check_password_hash 
from flask import session
from flask import Response
import csv
from io import StringIO
import datetime

app = Flask(__name__)


def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='gcoek',
        database='lbs3'
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
    cursor.execute("""
    SELECT MIN(id) AS id, title, author 
    FROM books 
    WHERE available > 0 
    GROUP BY title, author
""")
    books = cursor.fetchall()
    print("Books fetched:", books)

    
    cursor.execute("""
        SELECT b.title, b.author, br.borrow_date, br.return_date, br.status
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
    borrow_date = request.form['date_from']
    return_date = request.form['date_to']

    connection = get_db_connection()
    cursor = connection.cursor()

    
    cursor.execute("SELECT available FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()

    if book and book[0] > 0:
        
        cursor.execute("""
            INSERT INTO borrow_requests (user_id, book_id, borrow_date, return_date, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (user_id, book_id, borrow_date, return_date))

        
        cursor.execute("UPDATE books SET available = available - 1 WHERE id = %s", (book_id,))

        connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for('user_dashboard', user_id=user_id))

@app.route('/admin-dashboard', methods=['GET', 'POST'])
def admin_dashboard():  
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        
        # Check which button was clicked
        if 'approve' in request.form:
            cursor.execute("UPDATE borrow_requests SET status = 'approved' WHERE id = %s", (request_id,))
            connection.commit()
        elif 'deny' in request.form:
            cursor.execute("UPDATE borrow_requests SET status = 'denied' WHERE id = %s", (request_id,))
            connection.commit()

        # 2. Create New User
        elif 'create_user' in request.form:
            email = request.form['user_email']
            password = request.form['user_password']

            # OPTIONAL: hash password (recommended)
            # from werkzeug.security import generate_password_hash
            # password = generate_password_hash(password)

            # Check if user already exists
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing = cursor.fetchone()
            if existing:
                cursor.close()
                connection.close()
                return render_template('admin_dashboard.html', error='User already exists.')

            # Insert new user
            cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
            connection.commit()
            
    # Fetch all borrow requests
    cursor.execute("""
        SELECT br.id, u.email, b.title, br.status
        FROM borrow_requests br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
        WHERE br.status = "Pending"
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

        # Fetch all borrow records for the user, no status filter
        query = """
        SELECT 
            br.id AS request_id,
            br.book_id,
            b.title AS book_name,
            b.author AS author_name,
            br.borrow_date,
            br.return_date,
            br.status
        FROM 
            borrow_requests br
        JOIN 
            books b ON br.book_id = b.id
        WHERE 
            br.user_id = %s
        ORDER BY 
            br.borrow_date DESC
        """
        cursor.execute(query, (user_id,))
        borrowing_history = cursor.fetchall()

        print(f"Fetched {len(borrowing_history)} records for user {user_id}.")

        # Close DB connection
        cursor.close()
        connection.close()

        # Render the template with fetched history
        return render_template('user_history.html', borrowing_history=borrowing_history, user_id=user_id)

    except mysql.connector.Error as err:
        return f"Database Error: {err}"
    except Exception as e:
        return f"Unexpected Error: {e}"

@app.route('/mark-returned/<int:request_id>/<int:user_id>', methods=['POST'])
def mark_returned(request_id, user_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Mark book as returned
    cursor.execute("UPDATE borrow_requests SET status = 'Returned', return_date = CURDATE() WHERE id = %s", (request_id,))

    # Increase available count in books
    cursor.execute("""
        UPDATE books
        SET available = available + 1
        WHERE id = (SELECT book_id FROM borrow_requests WHERE id = %s)
    """, (request_id,))

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for('user_history', user_id=user_id))



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
        SELECT b.title, b.author, br.borrow_date, br.return_date, br.status
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
    writer.writerow(['Book Title', 'Author','From', 'To', 'Status'])  # Header row
    writer.writerows(borrow_history)  # Write data rows

    # Generate the response as a CSV file
    output.seek(0)
    return Response(
        output,
        
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=borrow_history_user_{user_id}.csv"}
    )
    
@app.route('/download-report/<string:period>')
def download_report(period):
    today = datetime.date.today()

    # Calculate start date based on period
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        start_date = today - datetime.timedelta(days=7)
    elif period == 'monthly':
        start_date = today - datetime.timedelta(days=30)
    else:
        return "Invalid period", 400

    # Connect and fetch data
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT br.id, u.email, b.title, b.author, br.borrow_date, br.return_date, br.status
        FROM borrow_requests br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
        WHERE br.borrow_date BETWEEN %s AND %s
    """, (start_date, today))

    records = cursor.fetchall()
    cursor.close()
    connection.close()

    # Prepare CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Request ID', 'User Email', 'Book Title', 'Author', 'From', 'To', 'Status'])
    for row in records:
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={period}_report_{today}.csv'
        }
    )


if __name__ == '__main__':
    app.run(debug=True)