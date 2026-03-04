from sqlmodel import Session, create_engine, select
from ingestion.models import Channel, Video
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def check_db():
    with Session(engine) as session:
        channels = session.exec(select(Channel)).all()
        videos = session.exec(select(Video)).all()
        print(f"Total Channels: {len(channels)}")
        print(f"Total Videos: {len(videos)}")
        
        for c in channels:
            print(f"Channel: {c.channel_name}, Status: {c.status}")

if __name__ == "__main__":
    check_db()
