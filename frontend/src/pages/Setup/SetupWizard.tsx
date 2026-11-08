import { useState, useEffect } from "react";
import axios from "axios";
import WelcomeStep from "./WelcomeStep";
import DatabaseStep from "./DatabaseStep";
import AccountStep from "./AccountStep";
import GlobalSettingsStep from "./GlobalSettingsStep";
import AuthStep from "./AuthStep";
import ServerStep from "./ServerStep";
import PeerStep from "./PeerStep";
import CompleteStep from "./CompleteStep";
import {
  saveSetupState,
  loadSetupState,
  clearSetupState,
  updateCurrentStep,
  type SetupStep,
} from "../../utils/setupStorage";
import { useAuthStore } from "../../store/auth";
import { api, authAPI, setupAPI } from "../../services/apiClient";

export default function SetupWizard({ serverStep }: { serverStep: string | null }) {
  const [currentStep, setCurrentStep] = useState<SetupStep>("welcome");
  const [setupData, setSetupData] = useState<any>({});
  const [showResumePrompt, setShowResumePrompt] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [savedState, setSavedState] = useState<any>(null);
  const [resumeUsername, setResumeUsername] = useState("");
  const [resumePassword, setResumePassword] = useState("");
  const [resumeError, setResumeError] = useState("");
  const [resumeLoading, setResumeLoading] = useState(false);
  const logout = useAuthStore((state) => state.logout);
  const login = useAuthStore((state) => state.login);
  const [needsAuth, setNeedsAuth] = useState(false);

  const steps: SetupStep[] = [
    "welcome",
    "database",
    "account",
    "globals",
    "auth",
    "server",
    "peer",
    "complete",
  ];
  const stepIndex = steps.indexOf(currentStep);

  // Check for saved setup state on mount
  useEffect(() => {
    const saved = loadSetupState();
    const validSteps: SetupStep[] = ["database", "account", "globals", "auth", "server", "peer", "complete"];
    const step = validSteps.includes(serverStep as SetupStep) ? serverStep as SetupStep : saved?.currentStep;
    if (step && step !== "welcome" && validSteps.includes(step)) {
      const data = { ...saved?.data } as any;
      if (serverStep === "peer") {
        delete data.serverId;
        delete data.serverName;
      }
      setSavedState({ currentStep: step, data, lastUpdated: saved?.lastUpdated });
      setShowResumePrompt(true);
    }
  }, [serverStep]);

  useEffect(() => {
    const requireAuth = () => {
      logout();
      setResumeUsername(setupData.username ?? "");
      setResumeError("Your setup session has expired. Sign in again to continue.");
      setNeedsAuth(true);
    };
    window.addEventListener("setup-auth-required", requireAuth);
    return () => window.removeEventListener("setup-auth-required", requireAuth);
  }, [logout, setupData.username]);

  const handleResumeSetup = async () => {
    if (savedState) {
      setResumeError("");
      const needsPassword = savedState.currentStep === "globals";
      let authenticated = false;
      const token = localStorage.getItem("token");
      if (token && !needsPassword) {
        try {
          const { data } = await axios.get(`${api.defaults.baseURL}/auth/profile`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          authenticated = data.role === "admin";
        } catch {
          authenticated = false;
        }
      }
      if (authenticated) login(token!, "admin");
      if (!authenticated && !needsPassword) logout();
      setCurrentStep(savedState.currentStep);
      setSetupData(savedState.data);
      setResumeUsername(savedState.data.username ?? "");
      setNeedsAuth(["globals", "auth", "server", "peer", "complete"].includes(savedState.currentStep) && !authenticated);
      setShowResumePrompt(false);
    }
  };

  const handleStartFresh = async () => {
    setResetting(true);
    try {
      await setupAPI.reset();
    } catch (e) {
      console.error("Setup reset failed:", e);
      setResumeError("Could not reset setup. Resume setup and sign in as an administrator before trying again.");
      return;
    } finally {
      setResetting(false);
    }
    clearSetupState();
    setShowResumePrompt(false);
    setConfirmReset(false);
    setCurrentStep("welcome");
    setSetupData({});
    setResumePassword("");
    setNeedsAuth(false);
  };

  const handleNext = (data?: any) => {
    const newData = data ? { ...setupData, ...data } : { ...setupData };
    if (currentStep === "account") setResumeUsername(newData.username ?? "");
    if (currentStep === "globals" && !localStorage.getItem("token")) setNeedsAuth(true);
    if (currentStep === "globals") delete newData.password;
    setSetupData(newData);

    // If WireGuard is missing at the server step, skip the peer step too
    const stepsToAdvance = data?.skipPeer ? 2 : 1;
    const nextIndex = stepIndex + stepsToAdvance;

    if (nextIndex < steps.length) {
      const nextStep = steps[nextIndex];
      saveSetupState({
        currentStep: nextStep,
        data: newData,
        lastUpdated: new Date().toISOString(),
      });
      updateCurrentStep(nextStep);
      setCurrentStep(nextStep);
    }
  };

  const handleBack = () => {
    setNeedsAuth(false);
    const prevIndex = stepIndex - 1;
    if (prevIndex >= 0) {
      const prevStep = steps[prevIndex];
      if (prevStep === "globals") setResumeUsername(setupData.username ?? "");
      setResumePassword("");
      setResumeError("");
      saveSetupState({
        currentStep: prevStep,
        data: setupData,
        lastUpdated: new Date().toISOString(),
      });
      updateCurrentStep(prevStep);
      setCurrentStep(prevStep);
    }
  };

  const handleComplete = () => {
    // Clear setup state when complete
    clearSetupState();
    // User is already logged in from AccountStep
    // Do a full page reload to refresh setup status in App.tsx
    window.location.href = "/dashboard";
  };

  const handleResumeCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setResumeError("");
    setResumeLoading(true);
    try {
      const data = await authAPI.setupLogin(resumeUsername, resumePassword);
      if (data.user?.role !== "admin") {
        setResumeError("An administrator account is required to continue setup.");
        return;
      }
      login(data.access_token, data.user?.role);
      setSetupData({ ...setupData, username: resumeUsername, ...(currentStep === "globals" ? { password: resumePassword } : {}) });
      setResumePassword("");
      setNeedsAuth(false);
    } catch (error) {
      const detail = axios.isAxiosError(error) && error.response?.status === 403 ? error.response.data?.detail : null;
      setResumeError(typeof detail === "string" ? detail : "Unable to sign in. Check your username and password and try again.");
    } finally {
      setResumeLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center p-4">
      {/* Resume Setup Prompt */}
      {showResumePrompt && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
        >
          <div role="dialog" aria-modal="true" aria-labelledby="resume-title"
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-md w-full border border-gray-200 dark:border-gray-700"
          >
            <h2 id="resume-title" className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              {confirmReset ? "Start Fresh?" : "Resume Setup?"}
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              {confirmReset ? "This will permanently delete the existing setup and its data. Continue?" :
                <>You have an incomplete setup{savedState?.lastUpdated ? ` from ${new Date(savedState.lastUpdated).toLocaleString()}` : ""}. Would you like to resume where you left off or start fresh?</>}
            </p>
            {resumeError && <p role="alert" className="mb-4 text-red-700 dark:text-red-400">{resumeError}</p>}
            <div className="flex gap-3">
              <button
                disabled={resetting}
                onClick={() => { setResumeError(""); setConfirmReset(!confirmReset); }}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                {confirmReset ? "Cancel" : "Start Fresh"}
              </button>
              <button
                disabled={resetting}
                onClick={confirmReset ? handleStartFresh : handleResumeSetup}
                className="flex-1 px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
              >
                {confirmReset ? (resetting ? "Resetting..." : "Confirm Reset") : "Resume Setup"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="w-full max-w-4xl">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Initial Setup</h1>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Step {stepIndex + 1} of {steps.length}
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-600 dark:bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 border border-gray-200 dark:border-gray-700">
          {!needsAuth && currentStep === "welcome" && <WelcomeStep onNext={handleNext} />}
          {!needsAuth && currentStep === "database" && <DatabaseStep onNext={handleNext} />}
          {!needsAuth && currentStep === "account" && (
            <AccountStep onNext={handleNext} onBack={handleBack} />
          )}
          {(needsAuth || (currentStep === "globals" && !setupData.password)) && (
            <form onSubmit={handleResumeCredentials} className="space-y-4">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Sign in to continue setup</h2>
              <p className="text-gray-600 dark:text-gray-300">Enter your admin credentials to continue. Your password is not saved.</p>
              {resumeError && <p role="alert" className="text-red-700 dark:text-red-400">{resumeError}</p>}
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Username
                <input name="username" autoComplete="username" required value={resumeUsername} onChange={(e) => setResumeUsername(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white" />
              </label>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Password
                <input name="password" type="password" autoComplete="current-password" required value={resumePassword} onChange={(e) => setResumePassword(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-white" />
              </label>
              <div className="flex justify-between">
                <button type="button" onClick={handleBack} className="px-6 py-2 text-gray-700 dark:text-gray-300">Back</button>
                <button type="submit" disabled={resumeLoading} className="rounded-lg bg-blue-600 dark:bg-blue-500 px-6 py-2 text-white disabled:opacity-50">{resumeLoading ? "Signing in..." : "Continue"}</button>
              </div>
            </form>
          )}
          {!needsAuth && currentStep === "globals" && setupData.password && (
            <GlobalSettingsStep onNext={handleNext} onBack={handleBack} setupData={setupData} />
          )}
          {!needsAuth && currentStep === "auth" && (
            <AuthStep onNext={handleNext} onBack={handleBack} setupData={setupData} />
          )}
          {!needsAuth && currentStep === "server" && (
            <ServerStep
              onNext={handleNext}
              onBack={handleBack}
              setupData={setupData}
            />
          )}
          {!needsAuth && currentStep === "peer" && (
            <PeerStep
              onNext={handleNext}
              onBack={handleBack}
              setupData={setupData}
            />
          )}
          {!needsAuth && currentStep === "complete" && (
            <CompleteStep setupData={setupData} onComplete={handleComplete} />
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
          <p>Linguard</p>
        </div>
      </div>
    </div>
  );
}
