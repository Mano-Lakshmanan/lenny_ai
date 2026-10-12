
from sqlalchemy import text
from database import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT VERSION()"))
        version = result.scalar()

        print("MySQL connection successful!")
        print("MySQL version:", version)

except Exception as error:
    print("MySQL connection failed.")
    print("Error:", error)
