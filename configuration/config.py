from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()


class Config(BaseModel):
    OPENAI_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_KEY"))


config = Config()
