/**
 * FieldError component - Displays validation error messages below form fields.
 * 
 * Usage:
 * <FieldError error={getFieldError(fieldErrors, 'field_name')} />
 */

interface FieldErrorProps {
  error?: string;
}

export default function FieldError({ error }: FieldErrorProps) {
  if (!error) {
    return null;
  }

  return (
    <div className="flex items-center gap-1 mt-1 text-sm text-red-600 dark:text-red-400">
      <svg 
        className="w-4 h-4 flex-shrink-0" 
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
      >
        <path 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          strokeWidth={2} 
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
        />
      </svg>
      <span>{error}</span>
    </div>
  );
}
