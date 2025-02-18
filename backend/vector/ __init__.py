import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set the OpenAI API key
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)