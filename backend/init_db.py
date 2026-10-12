
import models
from database import Base, engine

Base.metadata.create_all(bind=engine)

print("Database tables created successfully!")
print("Tables:", list(Base.metadata.tables.keys()))
