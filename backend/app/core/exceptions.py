"""
Custom exceptions and exception handlers for the Linguard API.

Provides standardized error responses with field-level validation errors.
"""

from typing import Dict, List, Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError


class ValidationError(Exception):
    """
    Exception for single field validation errors.
    
    Raises a validation error for a specific field with one or more error messages.
    """
    
    def __init__(self, field: str, messages: Union[str, List[str]]):
        """
        Initialize ValidationError.
        
        Args:
            field: The field name (e.g., 'name', 'endpoint', 'listen_port')
            messages: Error message(s) for the field
        """
        self.field = field
        self.messages = [messages] if isinstance(messages, str) else messages
        super().__init__(f"Validation error for field '{field}': {self.messages}")


class MultiFieldValidationError(Exception):
    """
    Exception for multiple field validation errors.
    
    Raises validation errors for multiple fields at once.
    """
    
    def __init__(self, errors: Dict[str, List[str]]):
        """
        Initialize MultiFieldValidationError.
        
        Args:
            errors: Dictionary mapping field names to lists of error messages
                    e.g., {'name': ['Name is required'], 'port': ['Port must be between 1-65535']}
        """
        self.errors = errors
        super().__init__(f"Validation errors: {errors}")


def format_validation_errors(errors: Dict[str, List[str]]) -> Dict[str, Dict[str, List[str]]]:
    """
    Format validation errors into the standardized response format.
    
    Args:
        errors: Dictionary of field names to error message lists
        
    Returns:
        Formatted error response: {"errors": {"body.field": ["message", ...]}}
    """
    formatted_errors = {}
    for field, messages in errors.items():
        # Add 'body.' prefix if not already present
        field_key = field if field.startswith('body.') else f'body.{field}'
        formatted_errors[field_key] = messages
    
    return {"errors": formatted_errors}


async def validation_exception_handler(
    request: Request, 
    exc: Union[RequestValidationError, PydanticValidationError]
) -> JSONResponse:
    """
    Custom exception handler for Pydantic validation errors.
    
    Transforms FastAPI/Pydantic validation errors into standardized format:
    {"errors": {"body.field_name": ["Error message 1", "Error message 2"]}}
    
    Args:
        request: The FastAPI request
        exc: The validation exception (RequestValidationError or PydanticValidationError)
        
    Returns:
        JSONResponse with 422 status and formatted errors
    """
    errors: Dict[str, List[str]] = {}
    model_level_errors: List[str] = []
    
    for error in exc.errors():
        # Extract the field path
        loc = error.get("loc", ())
        
        # Build the field key (e.g., "body.name" or "body.server.endpoint")
        if loc:
            # Skip 'body' if it's the first element, we'll add it back
            field_parts = [str(part) for part in loc if part != "body"]
            field_key = f"body.{'.'.join(field_parts)}" if field_parts else None
        else:
            field_key = None
        
        # Extract the error message and clean it up
        msg = error.get("msg", "Validation error")
        
        # Remove "Value error, " prefix that Pydantic adds
        if msg.startswith("Value error, "):
            msg = msg[13:]  # Remove "Value error, " (13 characters)
        
        # If field_key is None (model-level validation), save for later
        if field_key is None:
            model_level_errors.append(msg)
        else:
            # Add to errors dict
            if field_key not in errors:
                errors[field_key] = []
            errors[field_key].append(msg)
    
    # Handle model-level errors (e.g., "at least one IP required")
    # Attach them to relevant fields based on error message content
    for msg in model_level_errors:
        # Check if it's an IP address validation error
        if "IP address" in msg and ("IPv4" in msg or "IPv6" in msg):
            # Attach to both IP fields so user sees it on the form
            if "body.ipv4_address" not in errors:
                errors["body.ipv4_address"] = []
            if "body.ipv6_address" not in errors:
                errors["body.ipv6_address"] = []
            errors["body.ipv4_address"].append(msg)
            errors["body.ipv6_address"].append(msg)
        else:
            # Generic model-level error - attach to a "_form" key
            errors["body._form"] = [msg]
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errors": errors}
    )


async def custom_validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Handler for custom ValidationError exceptions.
    
    Args:
        request: The FastAPI request
        exc: The ValidationError exception
        
    Returns:
        JSONResponse with 422 status and formatted error
    """
    errors = {exc.field: exc.messages}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_validation_errors(errors)
    )


async def custom_multi_field_validation_error_handler(
    request: Request, 
    exc: MultiFieldValidationError
) -> JSONResponse:
    """
    Handler for custom MultiFieldValidationError exceptions.
    
    Args:
        request: The FastAPI request
        exc: The MultiFieldValidationError exception
        
    Returns:
        JSONResponse with 422 status and formatted errors
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_validation_errors(exc.errors)
    )
