# Ollama Grammar Correction API

## Overview

This project provides a simple REST API built with FastAPI that uses a locally running [Ollama](https://ollama.com/) instance to perform grammar and spelling correction on input text. It leverages a specified Ollama model (e.g., `gemma3`) to identify errors, suggest corrections, and provide the fully corrected sentence.

The API offers endpoints for correcting both single sentences and batches of sentences, returning structured JSON responses.

## Features

* **Grammar & Spelling Correction:** Utilizes Ollama language models for text correction.
* **RESTful API:** Exposes functionality via a clean FastAPI interface.
* **Single & Batch Processing:** Supports correcting one sentence or multiple sentences in a single request.
* **Detailed Corrections:** Provides information on the wrong word, the corrected word, and the reason for the correction.
* **Structured JSON:** Accepts and returns data in JSON format using Pydantic models for validation.
* **Includes Original Text:** The API response conveniently includes the original sentence submitted.
* **Retry Mechanism:** Implements basic retries for transient Ollama communication errors.
* **Interactive Docs:** Automatic API documentation provided by FastAPI (Swagger UI/ReDoc).

## Prerequisites

Before running this application, ensure you have the following installed and configured:

1.  **Python:** Version 3.8 or higher recommended.
2.  **Ollama:** Installed and running locally. You can download it from [ollama.com](https://ollama.com/).
3.  **Ollama Model:** The specific language model used by the API must be pulled into your Ollama instance. By default, this API uses `gemma3`. Pull it using:
    ```bash
    ollama pull gemma3
    ```
    *(If you modify `main.py` to use a different model, make sure to pull that model instead.)*
4.  **pip:** Python package installer.

## Installation

1.  **Clone the repository (or download `main.py`):**
    ```bash
    # If you have a git repository
    # git clone <your-repo-url>
    # cd <your-repo-directory>

    # Otherwise, just ensure you have the main.py file
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install fastapi uvicorn ollama pydantic httpx # httpx is used by ollama library
    ```
    *(Alternatively, if a `requirements.txt` file is provided: `pip install -r requirements.txt`)*

## Configuration

* **Ollama Model:** The Ollama model used is specified in `main.py` within the `get_corrections` function (defaults to `'gemma3'`). You can change this string if you wish to use a different compatible model available in your Ollama instance.
* **Ollama Host:** The application assumes Ollama is running on its default host (`http://localhost:11434`). If your Ollama instance runs elsewhere, you might need to configure the `ollama` client (refer to the `ollama-python` library documentation if needed, though often environment variables like `OLLAMA_HOST` work).

## Running the API

1.  **Ensure Ollama is running:** Start the Ollama application/service.
2.  **Start the FastAPI server using Uvicorn:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    * `main`: The name of the Python file (without `.py`).
    * `app`: The name of the FastAPI instance created in `main.py`.
    * `--reload`: Enables auto-reload on code changes (useful for development).
    * `--host 0.0.0.0`: Makes the server accessible on your network (use `127.0.0.1` for local access only).
    * `--port 8000`: Specifies the port number.

3.  **Access the API:**
    * **Interactive Docs (Swagger UI):** Open your browser to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    * **Alternative Docs (ReDoc):** Open your browser to [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## API Usage

The base URL for the API is `http://localhost:8000` (or as configured).

### Endpoint: `POST /correct/single`

Corrects a single sentence.

* **Request Body:**
    ```json
    {
      "text": "Thiss sentence has somee spelling mistaks."
    }
    ```

* **Successful Response (200 OK):**
    ```json
    {
      "corrections": [
        {
          "wrong_word": "Thiss",
          "correct_word": "This",
          "reason_of_error": "Spelling mistake."
        },
        {
          "wrong_word": "sentence",
          "correct_word": "sentence",
          "reason_of_error": "No error found." // Model might sometimes list words even if correct
        },
        {
          "wrong_word": "has",
          "correct_word": "has",
          "reason_of_error": "No error found."
        },
        {
          "wrong_word": "somee",
          "correct_word": "some",
          "reason_of_error": "Spelling mistake."
        },
        {
          "wrong_word": "spelling",
          "correct_word": "spelling",
          "reason_of_error": "No error found."
        },
        {
          "wrong_word": "mistaks",
          "correct_word": "mistakes",
          "reason_of_error": "Spelling mistake."
        }
      ],
      "correct_sentence": "This sentence has some spelling mistakes.",
      "original_sentence": "Thiss sentence has somee spelling mistaks."
    }
    ```
    *(Note: The exact `reason_of_error` and inclusion/exclusion of correct words depend on the Ollama model's output)*

* **Error Responses:**
    * `400 Bad Request`: Input text is empty.
    * `422 Unprocessable Entity`: Request body is malformed (e.g., missing `text` field).
    * `500 Internal Server Error`: Unexpected error during processing.
    * `502 Bad Gateway`: Ollama returned data that couldn't be parsed or validated against the expected format.
    * `503 Service Unavailable`: Could not connect to Ollama or Ollama returned a service error.

### Endpoint: `POST /correct/batch`

Corrects multiple sentences in a single request.

* **Request Body:**
    ```json
    {
      "texts": [
        "Frist sentence with errror.",
        "This one is okay.",
        "Anuther mistace here."
      ]
    }
    ```

* **Successful Response (200 OK):**
    Returns a list, where each item corresponds to the result for a sentence in the input list.
    ```json
    [
      {
        "corrections": [
          { "wrong_word": "Frist", "correct_word": "First", "reason_of_error": "Spelling mistake." },
          { "wrong_word": "errror", "correct_word": "error", "reason_of_error": "Spelling mistake." }
        ],
        "correct_sentence": "First sentence with error.",
        "original_sentence": "Frist sentence with errror."
      },
      {
        "corrections": [], // Or might list words with "No error found."
        "correct_sentence": "This one is okay.",
        "original_sentence": "This one is okay."
      },
      {
        "corrections": [
          { "wrong_word": "Anuther", "correct_word": "Another", "reason_of_error": "Spelling mistake." },
          { "wrong_word": "mistace", "correct_word": "mistake", "reason_of_error": "Spelling mistake." }
        ],
        "correct_sentence": "Another mistake here.",
        "original_sentence": "Anuther mistace here."
      }
    ]
    ```
    *(Note: If processing an individual sentence fails after retries, its corresponding item in the response list will contain an error message within the `correct_sentence` field and empty `corrections`)*

* **Error Responses:**
    * `400 Bad Request`: Input `texts` list is empty.
    * `422 Unprocessable Entity`: Request body is malformed (e.g., missing `texts` field or not a list).

## Error Handling

* The API validates input using Pydantic models.
* Errors during communication with Ollama (e.g., connection errors, timeouts, service errors) are caught, and relevant HTTP status codes (like 503) are returned.
* A basic retry mechanism is implemented for potentially transient Ollama errors (503, 504).
* If Ollama returns syntactically valid JSON but it doesn't match the expected structure (`OllamaResponse`), a 502 Bad Gateway error is returned.
* In the batch endpoint, if processing a single sentence fails persistently, an error message is included in its place in the response list, allowing the rest of the batch to potentially succeed.

## Technology Stack

* **Python:** Core programming language.
* **FastAPI:** Modern, fast web framework for building APIs.
* **Uvicorn:** ASGI server to run FastAPI.
* **Ollama:** Service for running local language models.
* **ollama-python:** Official Python client library for Ollama.
* **Pydantic:** Data validation and settings management.

## Future Improvements

* Implement asynchronous processing for the batch endpoint for better performance.
* Make retry attempts and delays configurable.
* Add authentication/API keys.
* Support selecting different Ollama models via API parameter or configuration.
* More granular error reporting in batch responses.
* Containerize the application using Docker.
