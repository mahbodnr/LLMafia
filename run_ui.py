"""
Script to run the Mafia game web UI.
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="mafia_game_ui.log"
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Mafia game web UI."""
    parser = argparse.ArgumentParser(description='Run the Mafia game web UI')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--debug', type=bool, default=False, help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Check if API keys are set
    required_keys = []
    if not os.getenv('OPENAI_API_KEY'):
        required_keys.append('OPENAI_API_KEY')
    if not os.getenv('ANTHROPIC_API_KEY'):
        required_keys.append('ANTHROPIC_API_KEY')
    if not os.getenv('GOOGLE_API_KEY'):
        required_keys.append('GOOGLE_API_KEY')
    
    if required_keys:
        print(f"Warning: The following API keys are not set: {', '.join(required_keys)}")
        print("Some LLM providers may not work without their API keys.")
        print("You can set them as environment variables or in a .env file.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            return
    
    try:
        # Import here to avoid circular imports
        from ui.app import app, socketio
        
        print(f"\n=== Mafia Game Web UI ===")
        print(f"Host: {args.host}")
        print(f"Port: {args.port}")
        print(f"Debug: {args.debug}")
        print("=========================\n")
        
        print(f"Starting web server at http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop the server")
        
        # Run the Flask app
        socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        logger.error(f"Error running server: {e}", exc_info=True)
        print(f"Error running server: {e}")
        print("Check mafia_game_ui.log for details.")


if __name__ == "__main__":
    main()
