import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import sqlite3
import warnings
from datetime import datetime
import pytz
import re
import os

# Suppress specific FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning, module="pyarrow.pandas_compat")

# Initial setup
st.title("Confirmation Form for Invoice Delivery and General Information")
st.write("Dear Madam/Sir, Here is the confirmation form for sending invoices and general information announcements from Sekolah Harapan Bangsa.")
st.write("Please ensure that the WA (WhatsApp) number and email formats are correct and currently active.")
st.write("If you wish to receive invoices separately for both Father and Mother with different WA numbers and emails, please fill out the form twice alternately.")

# Print the current working directory
print("Current working directory:", os.getcwd())

# Check if the database file exists
print("Database file exists:", os.path.isfile('responses.db'))

# Initialize SQLite database
conn = sqlite3.connect('responses.db')
c = conn.cursor()

# Drop the table if it exists to reset the schema
c.execute('DROP TABLE IF EXISTS responses')

# Create the table with the correct schema
c.execute('''
    CREATE TABLE responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade TEXT,
        student_name TEXT,
        parent_name TEXT,
        wa_active_parent TEXT,
        email_active_parent TEXT,
        signature BLOB,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Form fields
if 'grade' not in st.session_state:
    st.session_state.grade = ''
if 'student_name' not in st.session_state:
    st.session_state.student_name = ''
if 'parent_name' not in st.session_state:
    st.session_state.parent_name = ''
if 'wa_active_parent' not in st.session_state:
    st.session_state.wa_active_parent = ''
if 'email_active_parent' not in st.session_state:
    st.session_state.email_active_parent = ''

grade = st.selectbox("Grade", ["Grade 7A", "Grade 7B", "Grade 8A", "Grade 8B", "Grade 9A", "Grade 9B", "Grade 10", "Grade 11", "Grade 12"], index=0)
student_name = st.text_input("Student Name", st.session_state.student_name)
parent_name = st.text_input("Parent Name", st.session_state.parent_name)
wa_active_parent = st.text_input("WA Active Parent", st.session_state.wa_active_parent)
email_active_parent = st.text_input("Email Active Parent", st.session_state.email_active_parent)

# Signature
st.write("Signature:")
canvas_result = st_canvas(
    stroke_width=2,
    stroke_color="#000000",
    background_color="#FFFFFF",
    height=150,
    width=400,
    drawing_mode="freedraw",
    key="canvas"
)

# Email setup
your_name = "Sekolah Harapan Bangsa"
your_email = "shsmodernhill@shb.sch.id"
your_password = "jvvmdgxgdyqflcrf"

# Form validation
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_valid_phone(phone):
    return re.match(r"^\+?1?\d{9,15}$", phone)

if st.button("Submit"):
    # Validation checks
    if not student_name or not parent_name or not wa_active_parent or not email_active_parent:
        st.error("Please fill in all the required fields.")
    elif not is_valid_phone(wa_active_parent):
        st.error("Please enter a valid phone number in the format: +1234567890.")
    elif not is_valid_email(email_active_parent):
        st.error("Please enter a valid email address.")
    else:
        # Save signature
        signature_img = None
        if canvas_result.image_data is not None:
            img = Image.fromarray(canvas_result.image_data)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            signature_img = buf.getvalue()

        # Insert data into SQLite database
        try:
            c.execute('''
                INSERT INTO responses (grade, student_name, parent_name, wa_active_parent, email_active_parent, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (grade, student_name, parent_name, wa_active_parent, email_active_parent, signature_img))
            conn.commit()
            st.success("Form submitted successfully! Please kindly check your email. Thanks")
            # Print the data to verify insertion
            print("Data inserted:", (grade, student_name, parent_name, wa_active_parent, email_active_parent, signature_img))
        except sqlite3.Error as e:
            st.error(f"An error occurred: {e}")
            conn.rollback()

        # Generate PDF using template
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        
        # Current timestamp in GMT+7
        tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        can.drawString(100, 675, "Menyatakan dengan ini bahwa:")
        can.drawString(100, 650, f"Nama Peserta Didik           : {student_name}")
        can.drawString(100, 625, f"Kelas                                  : {grade}")
        can.drawString(100, 600, f"Nama Orang Tua               : {parent_name}")
        can.drawString(100, 575, f"WA aktif Orang Tua/Wali   : {wa_active_parent}")
        can.drawString(100, 550, f"Email aktif Orang Tua/Wali: {email_active_parent}")
        can.drawString(100, 500, f"Timestamp                           : {current_time}")

        if signature_img:
            signature_image = Image.open(io.BytesIO(signature_img))
            signature_path = "/tmp/signature.png"
            signature_image.save(signature_path)
            can.drawImage(signature_path, 400, 450, width=100, height=50)

        can.showPage()
        can.save()
        packet.seek(0)

        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(open("template.pdf", "rb"))
        output = PdfWriter()

        page = existing_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)

        output_stream = io.BytesIO()
        output.write(output_stream)
        output_stream.seek(0)

        # Prepare email
        msg = MIMEMultipart()
        msg["From"] = your_email
        msg["To"] = email_active_parent
        msg["Subject"] = "Form Submission Confirmation"
        body = "Dear Parent,\n\nThank you for your submission. Please find the attached confirmation form.\n\nBest regards,\nSekolah Harapan Bangsa"
        msg.attach(MIMEText(body, "plain"))

        # Attach PDF
        attachment = MIMEApplication(output_stream.read(), _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename="confirmation.pdf")
        msg.attach(attachment)

        # Send email
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(your_email, your_password)
                server.sendmail(your_email, email_active_parent, msg.as_string())
            st.success("Confirmation email sent successfully!")
        except Exception as e:
            st.error(f"Failed to send email: {e}")

# Admin login
admin_password = "adminpassword"
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    admin_username_input = st.sidebar.text_input("Admin Username")
    admin_password_input = st.sidebar.text_input("Admin Password", type="password")
    if admin_username_input == "admin" and admin_password_input == admin_password:
        st.session_state.admin_logged_in = True

if 'admin_logged_in' in st.session_state and st.session_state.admin_logged_in:
    st.sidebar.success("Logged in as Admin")

    if st.sidebar.button("Logout"):
        st.session_state.admin_logged_in = False
        st.sidebar.info("Logged out")

    # Display admin controls
    st.title("Admin Page")
    st.write("Download all form responses as an Excel file.")
    
    try:
        # Fetch data from SQLite database
        c.execute('SELECT id, grade, student_name, parent_name, wa_active_parent, email_active_parent, timestamp FROM responses')
        rows = c.fetchall()
        # Print the retrieved data for debugging
        print("Retrieved data:", rows)
        if not rows:
            st.write("No data available.")
        else:
            df = pd.DataFrame(rows, columns=["ID", "Grade", "Student Name", "Parent Name", "WA Active Parent", "Email Active Parent", "Timestamp"])
            st.write(df)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False)
            st.download_button(
                label="Download Excel",
                data=excel_buffer,
                file_name="form_responses.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # CRUD functionality
            st.write("Manage Responses")
            response_id = st.number_input("Response ID", min_value=1, step=1)
            action = st.selectbox("Action", ["View", "Update", "Delete"])

            if st.button("Execute"):
                if action == "View":
                    c.execute('SELECT * FROM responses WHERE id=?', (response_id,))
                    response = c.fetchone()
                    if response:
                        st.write(f"Grade: {response[1]}")
                        st.write(f"Student Name: {response[2]}")
                        st.write(f"Parent Name: {response[3]}")
                        st.write(f"WA Active Parent: {response[4]}")
                        st.write(f"Email Active Parent: {response[5]}")
                        st.write(f"Timestamp: {response[7]}")
                        if response[6]:
                            st.image(Image.open(io.BytesIO(response[6])), width=200)
                    else:
                        st.write("No response found with that ID.")
                elif action == "Update":
                    new_grade = st.selectbox("New Grade", ["Grade 7A", "Grade 7B", "Grade 8A", "Grade 8B", "Grade 9A", "Grade 9B", "Grade 10", "Grade 11", "Grade 12"])
                    new_student_name = st.text_input("New Student Name")
                    new_parent_name = st.text_input("New Parent Name")
                    new_wa_active_parent = st.text_input("New WA Active Parent")
                    new_email_active_parent = st.text_input("New Email Active Parent")
                    
                    if st.button("Update Response"):
                        try:
                            c.execute('''
                                UPDATE responses
                                SET grade=?, student_name=?, parent_name=?, wa_active_parent=?, email_active_parent=?
                                WHERE id=?
                            ''', (new_grade, new_student_name, new_parent_name, new_wa_active_parent, new_email_active_parent, response_id))
                            conn.commit()
                            st.success("Response updated successfully!")
                        except sqlite3.Error as e:
                            st.error(f"An error occurred: {e}")
                            conn.rollback()
                elif action == "Delete":
                    try:
                        c.execute('DELETE FROM responses WHERE id=?', (response_id,))
                        conn.commit()
                        st.success("Response deleted successfully!")
                    except sqlite3.Error as e:
                        st.error(f"An error occurred: {e}")
                        conn.rollback()
    except sqlite3.Error as e:
        st.error(f"An error occurred while fetching data: {e}")

# Close SQLite connection
conn.close()
