
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="Irrigation",
        user="postgres",
        password="123456",
        port="5432"
    )
