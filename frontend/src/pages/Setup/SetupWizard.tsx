import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import WelcomeStep from "./WelcomeStep";
import DatabaseStep from "./DatabaseStep";
import AccountStep from "./AccountStep";
import GlobalSettingsStep from "./GlobalSettingsStep";
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

export default function SetupWizard() {
  const [currentStep, setCurrentStep] = useState<SetupStep>("welcome");
  const [setupData, setSetupData] = useState<any>({});
  const [showResumePrompt, setShowResumePrompt] = useState(false);
  const [savedState, setSavedState] = useState<any>(null);
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  const steps: SetupStep[] = [
    "welcome",
    "database",
    "account",
    "globals",
    "server",
    "peer",
    "complete",
  ];
  const stepIndex = steps.indexOf(currentStep);

  // Check for saved setup state on mount
  useEffect(() => {
    const saved = loadSetupState();
    if (
      saved &&
      saved.currentStep !== "welcome" &&
      saved.currentStep !== "complete"
    ) {
      setSavedState(saved);
      setShowResumePrompt(true);
    }
  }, []);

  const handleResumeSetup = () => {
    if (savedState) {
      setCurrentStep(savedState.currentStep);
      setSetupData(savedState.data);
      setShowResumePrompt(false);
    }
  };

  const handleStartFresh = () => {
    clearSetupState();
    setShowResumePrompt(false);
    setCurrentStep("welcome");
    setSetupData({});
  };

  const handleNext = (data?: any) => {
    if (data) {
      const newData = { ...setupData, ...data };
      setSetupData(newData);

      // Save state to localStorage
      const nextIndex = stepIndex + 1;
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
    } else {
      const nextIndex = stepIndex + 1;
      if (nextIndex < steps.length) {
        const nextStep = steps[nextIndex];
        saveSetupState({
          currentStep: nextStep,
          data: setupData,
          lastUpdated: new Date().toISOString(),
        });
        updateCurrentStep(nextStep);
        setCurrentStep(nextStep);
      }
    }
  };

  const handleBack = () => {
    const prevIndex = stepIndex - 1;
    if (prevIndex >= 0) {
      const prevStep = steps[prevIndex];
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center p-4">
      {/* Resume Setup Prompt */}
      {showResumePrompt && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-50 p-4"
          onClick={handleStartFresh}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-md w-full border border-gray-200 dark:border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              Resume Setup?
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              You have an incomplete setup from{" "}
              {new Date(savedState?.lastUpdated).toLocaleString()}. Would you
              like to resume where you left off or start fresh?
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleStartFresh}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Start Fresh
              </button>
              <button
                onClick={handleResumeSetup}
                className="flex-1 px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
              >
                Resume Setup
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
          {currentStep === "welcome" && <WelcomeStep onNext={handleNext} />}
          {currentStep === "database" && <DatabaseStep onNext={handleNext} />}
          {currentStep === "account" && (
            <AccountStep onNext={handleNext} onBack={handleBack} />
          )}
          {currentStep === "globals" && (
            <GlobalSettingsStep onNext={handleNext} onBack={handleBack} setupData={setupData} />
          )}
          {currentStep === "server" && (
            <ServerStep
              onNext={handleNext}
              onBack={handleBack}
              setupData={setupData}
            />
          )}
          {currentStep === "peer" && (
            <PeerStep
              onNext={handleNext}
              onBack={handleBack}
              setupData={setupData}
            />
          )}
          {currentStep === "complete" && (
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
