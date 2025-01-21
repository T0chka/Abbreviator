import requests

def test_model_connection():
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3.1",
            "prompt": "Test prompt to verify connection.",
            "format": "json",
            "stream": False
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print("Model response:", data)

    except requests.exceptions.RequestException as e:
        print("Error connecting to the model:", e)

if __name__ == "__main__":
    test_model_connection()