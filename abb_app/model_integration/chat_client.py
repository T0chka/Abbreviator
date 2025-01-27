import json
import requests
import logging

logger = logging.getLogger(__name__)

class ChatModelClient:
    """Client for chat-based interaction with the model"""

    def __init__(self, host, model, temperature=0.6, top_p=0.6):
        self.host = host
        self.model = model
        self.temperature = temperature
        self.top_p = top_p

    def _send_request(self, prompt):
        """Send request to Ollama API"""
        try:
            response = requests.post(
                f'{self.host}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'temperature': self.temperature,
                    'top_p': self.top_p,
                    'format': 'json',
                    'stream': False
                }
            )
            response.raise_for_status()
            return response.json()['response']
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get model response: {str(e)}")

    def generate_response(self, prompt, rules):
        """Generate response with validation step"""
        # Get initial response
        # logger.info(f"Initial prompt: {prompt}") # Log initial prompt
        initial_response = self._send_request(prompt)
        try:
            initial = json.loads(initial_response)
            initial = initial.get('description', 'не знаю')
        except json.JSONDecodeError:
            initial = 'не знаю'
    
        logger.info(f"Initial response: {initial}")  # Log initial response

        # Add validation request to the same prompt
        validation_prompt = (
            f"Скорректируй расшифровку: '{initial}' для "
            f"{prompt}\n"
            f"в соответствии с этими правилами:\n{rules}\n"
            "Не повторяй неправильную расшифровку!"
        )
        # logger.info(f"Validation prompt: {validation_prompt}")  # Log validation prompt
        validation_response = self._send_request(validation_prompt)
        
        # Process responses
        try:
            corrected = json.loads(validation_response)
            logger.info(f"Corrected: {corrected}")
            return corrected.get('description', 'не знаю')
        except json.JSONDecodeError:
            try:
                initial = json.loads(initial_response)
                return initial.get('description', 'не знаю')
            except json.JSONDecodeError:
                return 'не знаю' 
            