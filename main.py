# main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
import json

# Attempt to import ollama, handle potential import error
try:
    from ollama import chat, ResponseError
except ImportError:
    print("Error: 'ollama' library not found.")
    print("Please install it using: pip install ollama")
    exit(1)  # Exit if ollama is not installed

# --- Pydantic Models ---


class Correction(BaseModel):
    """Correction data of the given sentence"""

    wrong_word: str
    correct_word: str
    reason_of_error: str


# NEW: Model defining the structure expected *from* Ollama
class Answer(BaseModel):
    """Structure expected back directly from Ollama."""

    corrections: List[Correction]
    correct_sentence: str


# NEW: Model defining the final API response structure (inherits from OllamaResponse)
class ApiResponse(Answer):
    """Structure for the final API response, including the original sentence."""

    original_sentence: str


# --- Input Models (remain the same) ---
class TextInput(BaseModel):
    """Input model for single text correction"""

    text: str


class TextListInput(BaseModel):
    """Input model for batch text correction"""

    texts: List[str]


# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Core Logic (Updated) ---


# Modified function to use OllamaResponse for parsing and ApiResponse for final output dict
def get_corrections(text: str) -> dict:
    """
    Calls the Ollama API to get grammar and spelling corrections.

    Args:
        text: The input sentence to correct.

    Returns:
        A dictionary matching the ApiResponse structure.

    Raises:
        ValueError: If the Ollama response cannot be parsed or validated.
        HTTPException: For Ollama API errors or other HTTP-related issues.
    """
    logger.info(f"Requesting correction for: '{text[:50]}...'")
    try:
        response = chat(
            messages=[
                {
                    "role": "user",
                    "content": f'Correct all the grammar and spelling errors in the following sentence. Try to give every answer. Respond ONLY with a JSON object matching the provided schema. Sentence: "{text}"',
                },
            ],
            model="gemma3",  # Make sure this model is available
            format=Answer.model_json_schema(),
            options={"temperature": 0},
        )

        # Validate and parse the JSON response using the Pydantic model
        if response and response.get("message") and response["message"].get("content"):
            content = response["message"]["content"]
            try:
                # Parse using the model expected *from* Ollama
                parsed_ollama_response = Answer.model_validate_json(content)

                # Create the final API response object, adding the original sentence
                final_response = ApiResponse(
                    corrections=parsed_ollama_response.corrections,
                    correct_sentence=parsed_ollama_response.correct_sentence,
                    original_sentence=text,  # Add the original text here
                )
                logger.info(f"Correction successful for: '{text[:50]}...'")
                # Return the dictionary representation for the API
                return final_response.model_dump()

            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to decode JSON response from Ollama: {json_err}")
                logger.error(f"Ollama raw response content: {content}")
                raise ValueError(
                    f"Ollama response was not valid JSON: {content}"
                ) from json_err
            except Exception as pydantic_err:  # Catch Pydantic validation errors
                logger.error(
                    f"Failed to validate Ollama response against schema {Answer.__name__}: {pydantic_err}"
                )
                logger.error(f"Ollama raw response content: {content}")
                raise ValueError(
                    f"Ollama response did not match expected format: {content}"
                ) from pydantic_err
        else:
            logger.error(f"Unexpected Ollama response structure: {response}")
            raise ValueError(f"Unexpected Ollama response structure: {response}")

    except ResponseError as e:
        logger.error(
            f"Ollama API error for text '{text[:50]}...': {e.status_code} - {e.error}"
        )
        raise HTTPException(
            status_code=503, detail=f"Ollama service error: {e.error}"
        ) from e
    except Exception as e:
        # Catch ValueErrors from parsing/validation above and raise as bad gateway/request?
        if isinstance(e, ValueError):
            logger.error(f"Data validation/parsing error for '{text[:50]}...': {e}")
            # Indicate that the upstream service (Ollama) provided bad data
            raise HTTPException(
                status_code=502, detail=f"Bad response from correction service: {e}"
            ) from e

        logger.error(
            f"An unexpected error occurred during correction for '{text[:50]}...': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error during correction: {e}"
        ) from e


# exception_wrapper remains the same conceptually, but now handles errors from the modified get_corrections
def exception_wrapper(text: str, max_retries: int = 5) -> dict:
    """
    Wraps the get_corrections call with a retry mechanism. Returns a dict matching ApiResponse.
    """
    retries = 0
    while retries < max_retries:
        try:
            # get_corrections now returns a dict matching ApiResponse
            return get_corrections(text)
        # Catch specific potentially recoverable errors (like Ollama service errors or bad gateway)
        except HTTPException as e:
            # Only retry specific server-side or connection issues, not client errors (4xx) or validation (502)
            if e.status_code in [503, 504]:  # Service Unavailable, Gateway Timeout
                retries += 1
                logger.warning(
                    f"Attempt {retries}/{max_retries + 1}: HTTP Error {e.status_code} processing '{text[:50]}...'. Retrying..."
                )
                logger.warning(f"Error details: {e.detail}")
                if retries > max_retries:
                    logger.error(
                        f"Max retries reached for text '{text[:50]}...'. Failing request with status {e.status_code}."
                    )
                    raise e  # Re-raise the last HTTPException
            else:
                # Don't retry other HTTP errors (like 4xx, 500, 502 from validation)
                logger.error(
                    f"Non-retryable HTTP Exception for text '{text[:50]}...': {e.status_code} - {e.detail}"
                )
                raise e
        except Exception as e:  # Catch other unexpected errors (should be rare if get_corrections handles well)
            logger.error(
                f"Unexpected non-HTTP error during wrapper execution for '{text[:50]}...': {e}",
                exc_info=True,
            )
            # Raise as a generic 500 Internal Server Error
            raise HTTPException(
                status_code=500, detail=f"Unexpected internal server error: {e}"
            ) from e

    # This should not be reached if exceptions are handled properly
    raise HTTPException(
        status_code=500,
        detail="Correction failed after multiple retries without specific error.",
    )


# --- FastAPI App (Updated response_model) ---
app = FastAPI(
    title="Grammar Correction API",
    description="Uses Ollama (gemma3 model) to correct grammar and spelling.",
    version="1.1.0",  # Bump version
)


# Use the new ApiResponse model for the response
@app.post(
    "/correct/single",
    response_model=ApiResponse,  # Use the final API response model
    summary="Correct a single sentence",
    tags=["Correction"],
)
def correct_single_text(input_data: TextInput):
    """
    Accepts a single sentence (`text`) and returns its corrected version
    along with details about the corrections made and the original sentence.
    """
    if not input_data.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")
    try:
        # exception_wrapper returns a dict that should match ApiResponse
        result_dict = exception_wrapper(input_data.text)
        # FastAPI validates the returned dict against the response_model (ApiResponse)
        return result_dict
    except HTTPException as e:
        raise e  # Re-raise exceptions handled by the wrapper/core logic
    except Exception as e:
        logger.error(
            f"Unhandled exception in /correct/single endpoint: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="An unexpected internal error occurred."
        )


# Use the new ApiResponse model for the response list items
@app.post(
    "/correct/batch",
    response_model=List[ApiResponse],  # Use a list of the final API response model
    summary="Correct a batch of sentences",
    tags=["Correction"],
)
def correct_batch_texts(input_data: TextListInput):
    """
    Accepts a list of sentences (`texts`) and returns a list of correction results,
    one for each input sentence. Each result includes the original sentence.
    """
    if not input_data.texts:
        raise HTTPException(status_code=400, detail="Input text list cannot be empty.")

    results = []
    for text in input_data.texts:
        if not text.strip():
            logger.warning("Skipping empty string in batch.")
            # Provide a response matching ApiResponse for the empty input
            results.append(
                ApiResponse(
                    original_sentence=text, corrections=[], correct_sentence=""
                ).model_dump()
            )
            continue

        try:
            # exception_wrapper returns a dict matching ApiResponse
            result_dict = exception_wrapper(text)
            results.append(result_dict)
        except HTTPException as e:
            logger.error(
                f"Failed processing item in batch: '{text[:50]}...'. Error: {e.status_code} - {e.detail}"
            )
            # Add an error representation matching ApiResponse structure
            results.append(
                ApiResponse(
                    original_sentence=text,
                    corrections=[],
                    correct_sentence=f"Error: {e.detail}",
                ).model_dump()
            )
        except Exception as e:
            logger.error(
                f"Unexpected error processing item in batch: '{text[:50]}...'. Error: {e}",
                exc_info=True,
            )
            results.append(
                ApiResponse(
                    original_sentence=text,
                    corrections=[],
                    correct_sentence="Error: Unexpected internal server error",
                ).model_dump()
            )

    return results  # FastAPI validates this list of dicts against List[ApiResponse]


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Grammar Correction API is running. See /docs for details."}


# --- Run the app (for local development) ---
if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI server...")
    print("Access the API documentation at http://127.0.0.1:8000/docs")
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=True
    )  # Ensure reload is on if needed
