import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { setupAPI } from "../../services/api";
import CustomSelect from "../../components/CustomSelect";

interface DatabaseStepProps {
  onNext: (data: any) => void;
}

type DatabaseType = "sqlite" | "postgresql" | "mysql";

export default function DatabaseStep({ onNext }: DatabaseStepProps) {
  const [selectedDatabase, setSelectedDatabase] =
    useState<DatabaseType>("sqlite");
  const [connectionString, setConnectionString] = useState("");
  const [error, setError] = useState<string | null>(null);

  const configureMutation = useMutation({
    mutationFn: setupAPI.configureDatabase,
    onSuccess: () => {
      onNext({
        database_type: selectedDatabase,
        connection_string: connectionString,
      });
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to configure database");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    setError(null);

    // Generate database_url based on type
    let database_url = "";
    if (selectedDatabase === "sqlite") {
      // For SQLite, use default path that backend will resolve
      // Backend uses: Path(__file__).parent.parent.parent / "data" / "linguard.db"
      database_url = "./data/linguard.db";
    } else if (connectionString.trim()) {
      database_url = connectionString.trim();
    } else {
      setError("Connection string is required for PostgreSQL and MySQL");
      return;
    }

    configureMutation.mutate({
      database_type: selectedDatabase,
      database_url: database_url,
    });
  };

  const getPlaceholder = () => {
    switch (selectedDatabase) {
      case "postgresql":
        return "postgresql+asyncpg://user:password@localhost:5432/database";
      case "mysql":
        return "mysql+aiomysql://user:password@localhost:3306/database";
      default:
        return "Not required for SQLite";
    }
  };

  const databaseOptions = [
    { value: "sqlite", label: "SQLite" },
    { value: "postgresql", label: "PostgreSQL" },
    { value: "mysql", label: "MySQL / MariaDB" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Choose Database
        </h2>
        <p className="text-gray-600 dark:text-gray-300">
          Select the database backend for Linguard.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Database Type
          </label>
          <CustomSelect
            value={selectedDatabase}
            onChange={(value) => setSelectedDatabase(value as DatabaseType)}
            options={databaseOptions}
          />
        </div>

        {selectedDatabase !== "sqlite" && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Connection String *
            </label>
            <input
              type="text"
              value={connectionString}
              onChange={(e) => setConnectionString(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
              placeholder={getPlaceholder()}
              required
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Full database connection URL with credentials
            </p>
          </div>
        )}

        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
          <div className="flex items-start">
            <svg
              className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mr-2 flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <p className="text-sm text-yellow-800 dark:text-yellow-400">
              <strong>Important:</strong> You won't be able to change this
              later.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end pt-4">
          <button
            type="submit"
            disabled={configureMutation.isPending}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:bg-blue-400 dark:disabled:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            {configureMutation.isPending ? "Configuring..." : "Continue"}
          </button>
        </div>
      </form>
    </div>
  );
}
