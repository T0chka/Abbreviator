import requests
import logging
import json
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class AbbreviationResponse(BaseModel):
    description: str

class ModelClient:
    def __init__(self, host="http://localhost:11434", model="llama3.2"):
        self.host = host
        self.model = model
        self.parser = PydanticOutputParser(pydantic_object=AbbreviationResponse)

    def generate_response(self, prompt: str):
        # format_instructions = self.parser.get_format_instructions()
        format_instructions = (
            " Ответ должен быть одним коротким предложением на одном языке"
            "в формате: {\"description\": \"<текст расшифровки>\"}"
        )
        prompt = f"{prompt}\n\n{format_instructions}"
        
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        payload_str = json.dumps(payload, indent=4, ensure_ascii=False)
        logger.debug(f"\nSending request to model at {url} with payload:\n{payload_str}")
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            response_data.pop("context", None)
            response_str = json.dumps(response_data, indent=4, ensure_ascii=False)
            logger.debug(f"Model response:\n{response_str}")

            description = self.parser.parse(response_data.get("response", ""))

            return description.description
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to the model: {e}")
            raise
        except ValueError as e:
            logger.error(f"Failed to parse model response: {e}")
            raise