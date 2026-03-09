import { useQuery } from '@tanstack/react-query';
import { systemAPI, versionAPI } from '../services/api';

interface SystemInfo {
  app: {
    name: string;
    version: string;
    python_version: string;
    git_commit: string;
    git_commit_short: string;
    uptime_seconds: number;
  };
  host: {
    hostname: string;
    os: string;
    os_release: string;
    os_version: string;
    architecture: string;
    cpu_count: number;
    cpu_percent: number;
    ram_total_bytes: number;
    ram_used_bytes: number;
    ram_available_bytes: number;
    ram_percent: number;
  };
}

interface UpdateInfo {
  update_available: boolean;
  latest_version?: string;
  release_url?: string;
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(' ');
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function usageColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500';
  if (percent >= 70) return 'bg-yellow-400';
  return 'bg-blue-500';
}

function InfoRow({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between py-3 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <span className="text-sm text-gray-500 dark:text-gray-400 shrink-0 w-40">{label}</span>
      <span className={`text-sm text-gray-900 dark:text-gray-100 text-right break-all ${mono ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}

function UsageBar({ label, percent, detail }: { label: string; percent: number; detail: string }) {
  return (
    <div className="py-3 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
        <span className="text-sm text-gray-900 dark:text-gray-100">{detail}</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
        <div
          className={`${usageColor(percent)} h-1.5 rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function SystemInfo() {
  const { data: sysInfo, isLoading, error } = useQuery<SystemInfo>({
    queryKey: ['system-info'],
    queryFn: systemAPI.getInfo,
    refetchInterval: 10000,
  });

  const { data: updateInfo } = useQuery<UpdateInfo>({
    queryKey: ['version-check'],
    queryFn: versionAPI.checkUpdates,
    staleTime: Infinity,
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">System Info</h1>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-300">
          Failed to load system information.
        </div>
      )}

      {sysInfo && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          {/* Host */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">System</h2>
            </div>
            <div className="px-6">
              <InfoRow label="Hostname" value={sysInfo.host.hostname} mono />
              <InfoRow label="OS" value={sysInfo.host.os} />
              <InfoRow label="Kernel" value={sysInfo.host.os_release} mono />
              <InfoRow label="Architecture" value={sysInfo.host.architecture} mono />
              <InfoRow label="Python version" value={sysInfo.app.python_version.split(' ')[0]} mono />
              <InfoRow label="CPU cores" value={sysInfo.host.cpu_count} />
              <UsageBar
                label="CPU usage"
                percent={sysInfo.host.cpu_percent}
                detail={`${sysInfo.host.cpu_percent.toFixed(1)}%`}
              />
              <UsageBar
                label="RAM usage"
                percent={sysInfo.host.ram_percent}
                detail={`${formatBytes(sysInfo.host.ram_used_bytes)} / ${formatBytes(sysInfo.host.ram_total_bytes)} (${sysInfo.host.ram_percent.toFixed(1)}%)`}
              />
            </div>
          </div>

          {/* Application */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">{sysInfo.app.name}</h2>
            </div>
            <div className="px-6">
              <InfoRow
                label="Version"
                value={
                  <span className="flex items-center gap-2 justify-end">
                    v{sysInfo.app.version}
                    {updateInfo?.update_available && updateInfo.release_url && (
                      <a
                        href={updateInfo.release_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300 hover:underline"
                      >
                        v{updateInfo.latest_version} available
                      </a>
                    )}
                  </span>
                }
              />
              <InfoRow
                label="Git commit"
                value={
                  sysInfo.app.git_commit ? (
                    <span className="font-mono text-gray-900 dark:text-gray-100" title={sysInfo.app.git_commit}>
                      {sysInfo.app.git_commit_short}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )
                }
              />
              <InfoRow label="Uptime" value={formatUptime(sysInfo.app.uptime_seconds)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
