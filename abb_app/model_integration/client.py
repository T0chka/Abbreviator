import requests
import logging
import json
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel
from django.conf import settings

logger = logging.getLogger(__name__)

class ModelClient:
    def __init__(
            self,
            host=getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434'),
            model=getattr(settings, 'OLLAMA_MODEL', 'llama3.1'),
            temperature=getattr(settings, 'OLLAMA_TEMPERATURE', 0.9),
            top_p=getattr(settings, 'OLLAMA_TOP_P', 0.9)
        ):
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
                },
                timeout=3
            )
            response.raise_for_status()
            return response.json()['response']
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error to Ollama server at {self.host}")
            return json.dumps({"description": "Sorry, the language model service is unavailable now"})
        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to Ollama server at {self.host}")
            return json.dumps({"description": "Sorry, the language model service is unavailable now"})
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from Ollama server: {e}")
            return json.dumps({"description": "Sorry, the language model service is unavailable now"})
        except Exception as e:
            logger.error(f"Unexpected error with Ollama server: {str(e)}")
            return json.dumps({"description": "Sorry, the language model service is unavailable now"})

    def generate_response(self, prompt: str):
        format_instructions = (
            "Ответ должен быть в формате JSON: {\"description\": \"<текст расшифровки>\"}"
        )
        prompt = f"{prompt}\n{format_instructions}"        
        # logger.info(f"Prompt: {prompt}")
        response = self._send_request(prompt)
        try:
            response_json = json.loads(response)
            return response_json.get("description", "")
            
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse model response: {e}")
            raise