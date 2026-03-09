export interface ToggleSwitchProps {
  id?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}

export default function ToggleSwitch({
  id,
  checked,
  onChange,
  disabled = false,
  label,
  className = "",
}: ToggleSwitchProps) {
  const handleToggle = () => {
    if (!disabled) {
      onChange(!checked);
    }
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={id ? `${id}-label` : undefined}
        disabled={disabled}
        onClick={handleToggle}
        className={`
          relative inline-flex h-6 w-11 items-center rounded-full
          transition-colors duration-200 ease-in-out focus:outline-none 
          focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 
          focus:ring-offset-2 dark:focus:ring-offset-gray-800
          ${
            checked
              ? "bg-blue-600 dark:bg-blue-500"
              : "bg-gray-300 dark:bg-gray-600"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
      >
        <span
          className={`
            inline-block h-5 w-5 transform rounded-full bg-white 
            shadow-sm transition-transform duration-200 ease-in-out
            ${checked ? "translate-x-5" : "translate-x-0.5"}
          `}
        />
      </button>
      {label && (
        <label
          id={id ? `${id}-label` : undefined}
          htmlFor={id}
          className={`text-sm font-medium text-gray-700 dark:text-gray-300 ${
            disabled ? "opacity-50" : "cursor-pointer"
          }`}
          onClick={handleToggle}
        >
          {label}
        </label>
      )}
    </div>
  );
}
