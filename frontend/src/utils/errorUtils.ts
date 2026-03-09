/**
 * Error handling utilities for parsing and displaying API validation errors.
 * 
 * Handles the standardized error format from the backend:
 * { "errors": { "body.field_name": ["error message 1", "error message 2"] } }
 */

export interface FieldErrors {
  [key: string]: string[];
}

/**
 * Check if an error response is a validation error (status 422).
 * 
 * @param error - The error object from the API
 * @returns True if the error is a validation error
 */
export function isValidationError(error: any): boolean {
  return error?.response?.status === 422;
}

/**
 * Parse validation errors from the API response into a field-error map.
 * 
 * Transforms backend format { "errors": { "body.field": ["msg"] } }
 * into frontend format { "field": ["msg"] }
 * 
 * @param error - The error object from the API
 * @returns Object mapping field names to arrays of error messages
 */
export function parseValidationErrors(error: any): FieldErrors {
  if (!error?.response?.data?.errors) {
    return {};
  }

  const backendErrors = error.response.data.errors;
  const fieldErrors: FieldErrors = {};

  // Transform "body.field_name" to "field_name"
  for (const [key, messages] of Object.entries(backendErrors)) {
    // Remove "body." prefix if present
    const fieldName = key.startsWith('body.') ? key.substring(5) : key;
    fieldErrors[fieldName] = messages as string[];
  }

  return fieldErrors;
}

/**
 * Get the first error message for a specific field.
 * 
 * @param fieldErrors - The field errors object
 * @param fieldName - The name of the field
 * @returns The first error message for the field, or undefined if no error
 */
export function getFieldError(fieldErrors: FieldErrors, fieldName: string): string | undefined {
  const errors = fieldErrors[fieldName];
  return errors && errors.length > 0 ? errors[0] : undefined;
}

/**
 * Count the total number of validation errors across all fields.
 * 
 * @param fieldErrors - The field errors object
 * @returns The total number of error messages
 */
export function countErrors(fieldErrors: FieldErrors): number {
  return Object.values(fieldErrors).reduce((total, errors) => total + errors.length, 0);
}

/**
 * Extract a generic error message from a non-validation error.
 * Falls back to a default message if no message is available.
 * 
 * @param error - The error object from the API
 * @param defaultMessage - Default message to use if no error message is found
 * @returns The error message
 */
export function getGenericError(error: any, defaultMessage: string = 'An error occurred'): string {
  // Try to get the error message from various possible locations
  if (error?.response?.data?.detail) {
    return error.response.data.detail;
  }
  if (error?.response?.data?.message) {
    return error.response.data.message;
  }
  if (error?.message) {
    return error.message;
  }
  return defaultMessage;
}

/**
 * Check if there are any errors for a specific field.
 * 
 * @param fieldErrors - The field errors object
 * @param fieldName - The name of the field
 * @returns True if the field has errors
 */
export function hasFieldError(fieldErrors: FieldErrors, fieldName: string): boolean {
  return !!fieldErrors[fieldName] && fieldErrors[fieldName].length > 0;
}

/**
 * Clear errors for specific fields.
 * 
 * @param fieldErrors - The current field errors object
 * @param fieldNames - Array of field names to clear errors for
 * @returns New field errors object with specified fields cleared
 */
export function clearFieldErrors(fieldErrors: FieldErrors, fieldNames: string[]): FieldErrors {
  const newErrors = { ...fieldErrors };
  fieldNames.forEach(field => {
    delete newErrors[field];
  });
  return newErrors;
}

/**
 * Format validation error count for user display.
 * 
 * @param count - Number of validation errors
 * @returns Formatted error message
 */
export function formatErrorCount(count: number): string {
  if (count === 1) {
    return '1 validation error found';
  }
  return `${count} validation errors found`;
}
