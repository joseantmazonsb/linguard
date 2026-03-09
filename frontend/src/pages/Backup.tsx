import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-toastify';
import { backupAPI } from '../services/api';
import ToggleSwitch from '../components/ToggleSwitch';
import ConfirmDialog from '../components/ConfirmDialog';

interface Backup {
  id: number;
  filename: string;
  description?: string;
  file_size: number;
  is_encrypted: boolean;
  created_by_id: number;
  created_by_username: string;
  created_at: string;
}

export default function Backup() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [showRestoreConfirmModal, setShowRestoreConfirmModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    isOpen: boolean;
    backup: Backup | null;
  }>({
    isOpen: false,
    backup: null,
  });
  const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null);
  const [createData, setCreateData] = useState({
    description: '',
  });
  const [restoreData, setRestoreData] = useState({
    overwrite: true,
  });
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importDescription, setImportDescription] = useState('');
  const queryClient = useQueryClient();

  // Fetch backups
  const { data: backups, isLoading, error } = useQuery({
    queryKey: ['backups'],
    queryFn: backupAPI.list,
  });

  // Fetch statistics
  const { data: stats } = useQuery({
    queryKey: ['backup-stats'],
    queryFn: backupAPI.getStats,
  });

  // Create backup mutation
  const createMutation = useMutation({
    mutationFn: backupAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backups'] });
      queryClient.invalidateQueries({ queryKey: ['backup-stats'] });
      setShowCreateModal(false);
      setCreateData({ description: '' });
      toast.success('Backup created successfully!');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to create backup';
      toast.error(message);
    },
  });

  // Restore backup mutation
  const restoreMutation = useMutation({
    mutationFn: ({ id, overwrite }: { id: number; overwrite: boolean }) =>
      backupAPI.restore(id, undefined, overwrite),
    onSuccess: () => {
      queryClient.invalidateQueries();
      setShowRestoreModal(false);
      setShowRestoreConfirmModal(false);
      setSelectedBackup(null);
      setRestoreData({ overwrite: true });
      toast.success('Backup restored successfully!');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to restore backup';
      toast.error(message);
    },
  });

  // Delete backup mutation
  const deleteMutation = useMutation({
    mutationFn: backupAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backups'] });
      queryClient.invalidateQueries({ queryKey: ['backup-stats'] });
      toast.success('Backup deleted successfully!');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete backup';
      toast.error(message);
    },
  });

  // Import backup mutation
  const importMutation = useMutation({
    mutationFn: ({ file, description }: { file: File; description?: string }) =>
      backupAPI.upload(file, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backups'] });
      queryClient.invalidateQueries({ queryKey: ['backup-stats'] });
      setShowImportModal(false);
      setImportFile(null);
      setImportDescription('');
      toast.success('Backup imported successfully!');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to import backup';
      toast.error(message);
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(createData);
  };

  const handleRestoreSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBackup) return;

    // Show confirmation modal
    setShowRestoreModal(false);
    setShowRestoreConfirmModal(true);
  };

  const handleRestoreConfirm = () => {
    if (!selectedBackup) return;
    
    restoreMutation.mutate({
      id: selectedBackup.id,
      overwrite: restoreData.overwrite,
    });
  };

  const handleImportSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) {
      toast.error('Please select a file to import');
      return;
    }
    importMutation.mutate({ file: importFile, description: importDescription });
  };

  const handleDownload = async (backup: Backup) => {
    try {
      const blob = await backupAPI.download(backup.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = backup.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      toast.error('Failed to download backup');
    }
  };

  const handleDelete = (backup: Backup) => {
    setDeleteConfirm({
      isOpen: true,
      backup,
    });
  };

  const handleConfirmDelete = () => {
    if (deleteConfirm.backup) {
      deleteMutation.mutate(deleteConfirm.backup.id);
      setDeleteConfirm({ isOpen: false, backup: null });
    }
  };

  const handleCancelDelete = () => {
    setDeleteConfirm({ isOpen: false, backup: null });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500 dark:text-gray-400">Loading backups...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded">
          Error loading backups: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">Backup & Restore</h1>
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400">
            Create and manage system backups
          </p>
        </div>
        <div className="flex gap-2 sm:gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-800 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base"
          >
            <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span className="hidden sm:inline">Import Backup</span>
            <span className="sm:hidden">Import</span>
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 text-white px-3 sm:px-4 py-2 rounded-lg flex items-center gap-2 transition-colors text-sm sm:text-base"
          >
            <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span className="hidden sm:inline">Create Backup</span>
            <span className="sm:hidden">Create</span>
          </button>
        </div>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:shadow-gray-900">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Backups</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_backups || 0}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:shadow-gray-900">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Size</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatFileSize(stats.total_size || 0)}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:shadow-gray-900">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Latest Backup</div>
            <div className="text-sm text-gray-900 dark:text-gray-300">
              {stats.latest_backup ? formatDate(stats.latest_backup.created_at) : 'None'}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow dark:shadow-gray-900">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Oldest Backup</div>
            <div className="text-sm text-gray-900 dark:text-gray-300">
              {stats.oldest_backup ? formatDate(stats.oldest_backup.created_at) : 'None'}
            </div>
          </div>
        </div>
      )}

      {/* Backups Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {backups && backups.length > 0 ? (
          backups.map((backup: Backup) => (
            <div key={backup.id} className="bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md dark:shadow-gray-900 dark:hover:shadow-gray-900 transition-shadow border dark:border-gray-700">
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                      {backup.filename}
                    </h3>
                    {backup.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{backup.description}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    {formatFileSize(backup.file_size)}
                  </div>
                  <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    {backup.created_by_username}
                  </div>
                  <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {formatDate(backup.created_at)}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setSelectedBackup(backup);
                      setShowRestoreModal(true);
                    }}
                    className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 text-white text-sm rounded-lg transition-colors"
                  >
                    Restore
                  </button>
                  <button
                    onClick={() => handleDownload(backup)}
                    className="px-3 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 text-sm rounded-lg transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  </button>
                  <button
                    onClick={() => handleDelete(backup)}
                    className="px-3 py-2 bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-800 text-white text-sm rounded-lg transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full bg-gray-50 dark:bg-gray-800 rounded-lg p-12 text-center border dark:border-gray-700">
            <svg className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No backups yet</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">Create your first backup to get started</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 text-white px-4 py-2 rounded-lg transition-colors"
            >
              Create Backup
            </button>
          </div>
        )}
      </div>

      {/* Create Backup Modal */}
      {showCreateModal && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center p-4 z-50"
          onClick={() => {
            setShowCreateModal(false);
            setCreateData({ description: '' });
          }}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <form onSubmit={handleCreateSubmit}>
              <div className="p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Create Backup</h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Description (Optional)
                    </label>
                    <input
                      type="text"
                      value={createData.description}
                      onChange={(e) => setCreateData({ ...createData, description: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                      placeholder="Full system backup"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateData({ description: '' });
                  }}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 disabled:bg-blue-400 dark:disabled:bg-blue-900 text-white rounded-lg font-medium transition-colors"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Backup'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Restore Backup Modal */}
      {showRestoreModal && selectedBackup && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center p-4 z-50"
          onClick={() => {
            setShowRestoreModal(false);
            setSelectedBackup(null);
            setRestoreData({ overwrite: true });
          }}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <form onSubmit={handleRestoreSubmit}>
              <div className="p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Restore Backup</h2>

                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-4">
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <h3 className="text-sm font-semibold text-yellow-900 dark:text-yellow-200">Warning</h3>
                      <p className="text-sm text-yellow-800 dark:text-yellow-300 mt-1">
                        All existing servers and peers will be deleted before restoring this backup.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Backup File</label>
                    <div className="text-gray-900 dark:text-white">{selectedBackup.filename}</div>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => {
                    setShowRestoreModal(false);
                    setSelectedBackup(null);
                    setRestoreData({ overwrite: true });
                  }}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={restoreMutation.isPending}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 disabled:bg-blue-400 dark:disabled:bg-blue-900 text-white rounded-lg font-medium transition-colors"
                >
                  {restoreMutation.isPending ? 'Restoring...' : 'Restore'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Backup Modal */}
      {showImportModal && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center p-4 z-50"
          onClick={() => {
            setShowImportModal(false);
            setImportFile(null);
            setImportDescription('');
          }}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <form onSubmit={handleImportSubmit}>
              <div className="p-6">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Import Backup</h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Backup File *
                    </label>
                    <input
                      type="file"
                      accept=".json"
                      onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      required
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Select a backup JSON file to import
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Description (Optional)
                    </label>
                    <input
                      type="text"
                      value={importDescription}
                      onChange={(e) => setImportDescription(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                      placeholder="Imported from production"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t dark:border-gray-700">
                <button
                  type="button"
                  onClick={() => {
                    setShowImportModal(false);
                    setImportFile(null);
                    setImportDescription('');
                  }}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={importMutation.isPending || !importFile}
                  className="px-6 py-2 bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-800 disabled:bg-green-400 dark:disabled:bg-green-900 text-white rounded-lg font-medium transition-colors"
                >
                  {importMutation.isPending ? 'Importing...' : 'Import Backup'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {showRestoreConfirmModal && selectedBackup && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center p-4 z-50"
          onClick={() => {
            setShowRestoreConfirmModal(false);
            setSelectedBackup(null);
            setRestoreData({ overwrite: false });
          }}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full border dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-center w-12 h-12 mx-auto bg-yellow-100 dark:bg-yellow-900/30 rounded-full mb-4">
                <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>

              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2 text-center">Confirm Restore</h2>
              <p className="text-gray-600 dark:text-gray-400 text-center mb-6">
                Are you sure you want to restore this backup? All existing servers and peers will be deleted before restoring.
              </p>

              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 mb-6">
                <div className="text-sm text-gray-700 dark:text-gray-300">
                  <div className="flex justify-between mb-2">
                    <span className="font-medium">Backup:</span>
                    <span>{selectedBackup.filename}</span>
                  </div>
                  {selectedBackup.description && (
                    <div className="flex justify-between mb-2">
                      <span className="font-medium">Description:</span>
                      <span>{selectedBackup.description}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="font-medium">Created:</span>
                    <span>{formatDate(selectedBackup.created_at)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-900 px-6 py-4 flex items-center justify-end gap-3 rounded-b-lg border-t dark:border-gray-700">
              <button
                type="button"
                onClick={() => {
                  setShowRestoreConfirmModal(false);
                  setShowRestoreModal(true);
                }}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Go Back
              </button>
              <button
                type="button"
                onClick={handleRestoreConfirm}
                disabled={restoreMutation.isPending}
                className="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 dark:bg-yellow-700 dark:hover:bg-yellow-800 disabled:bg-yellow-400 dark:disabled:bg-yellow-900 text-white rounded-lg font-medium transition-colors"
              >
                {restoreMutation.isPending ? 'Restoring...' : 'Yes, Restore Backup'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        title="Delete Backup"
        message={
          deleteConfirm.backup
            ? `Are you sure you want to delete the backup "${deleteConfirm.backup.filename}"? This action cannot be undone.`
            : ''
        }
        confirmText="Delete"
        confirmStyle="danger"
      />
    </div>
  );
}
