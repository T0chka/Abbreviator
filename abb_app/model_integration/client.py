import requests
import logging
import json
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel
from django.conf import settings

logger = logging.getLogger(__name__)

class AbbreviationResponse(BaseModel):
    description: str

class ModelClient:
    def __init__(
            self,
            host=getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434'),
            model=getattr(settings, 'OLLAMA_MODEL', 'llama3.2'),
            temperature=getattr(settings, 'OLLAMA_TEMPERATURE', 0.6),
            top_p=getattr(settings, 'OLLAMA_TOP_P', 0.6)
        ):
        self.host = host
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.parser = PydanticOutputParser(pydantic_object=AbbreviationResponse)
        
    def _clean_response(self, text: str) -> str:
        """Clean and validate model response"""
        # Remove any markdown formatting
        text = text.replace('```json', '').replace('```', '').strip()
        
        # Try to find JSON-like structure if response contains extra text
        if '{' in text and '}' in text:
            start = text.find('{')
            end = text.rfind('}') + 1
            text = text[start:end]
            
        return text

    def generate_response(self, prompt: str):
        format_instructions = (
            " Ответ должен быть одним коротким предложением на одном языке"
            "в формате JSON: {\"description\": \"<текст расшифровки>\"}"
        )
        prompt = f"{prompt}\n\n{format_instructions}"
        
        url = f"{self.host}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "temperature": self.temperature,
            "top_p": self.top_p
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            response_data.pop("context", None)
            
            # Clean and parse response
            model_response = response_data.get("response", "")
            cleaned_response = self._clean_response(model_response)
            
            try:
                # First try to parse as JSON
                response_json = json.loads(cleaned_response)
                description = response_json.get("description", "")
            except json.JSONDecodeError:
                # If JSON parsing fails, try using the pydantic parser
                description = self.parser.parse(cleaned_response).description
            
            if not description:
                raise ValueError("Empty description received")
            
            return description
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to the model: {e}")
            raise
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse model response: {e}")
            raise