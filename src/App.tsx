import React, { useState, useEffect } from 'react';
import { useShiftStore } from './core/store';
import { Header } from './components/Header';
import { ATBQueue } from './components/ATBQueue';
import { ZoneView } from './components/ZoneView';
import { EquipmentView } from './components/EquipmentView';
import { CrewView } from './components/CrewView';
import { AllocationWizard } from './components/AllocationWizard';
import { SettingsModal } from './components/SettingsModal';

export const App: React.FC = () => {
  const { tick, recomputePlan } = useShiftStore();

  const [currentView, setCurrentView] = useState<'zones' | 'equipment' | 'crew'>('zones');
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);

  // Periodic tick for live clock and scheduling
  useEffect(() => {
    recomputePlan();
    const timer = setInterval(() => {
      tick();
    }, 1000);
    return () => clearInterval(timer);
  }, [tick, recomputePlan]);

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Application Bar */}
      <Header
        currentView={currentView}
        onViewChange={setCurrentView}
        onOpenWizard={() => setIsWizardOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Main Workspace Body */}
      <div className="flex-1 flex min-h-0 relative overflow-hidden">
        {/* Toggleable Relief Floater Sidebar */}
        {showSidebar && <ATBQueue />}

        {/* Sidebar Toggle Tab */}
        <button
          onClick={() => setShowSidebar(!showSidebar)}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-30 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white px-1 py-3 rounded-r-lg border border-l-0 border-slate-700 text-[10px] font-bold shadow-md cursor-pointer transition-all"
          style={{ left: showSidebar ? '288px' : '0px' }}
          title={showSidebar ? 'Hide Floater Sidebar' : 'Show Floater Sidebar'}
        >
          {showSidebar ? '◀' : '▶'}
        </button>

        {/* Scrollable Dashboard View */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-slate-950">
          <div className="max-w-7xl mx-auto pb-12">
            {currentView === 'zones' && <ZoneView />}
            {currentView === 'equipment' && <EquipmentView />}
            {currentView === 'crew' && <CrewView />}
          </div>
        </main>
      </div>

      {/* Allocation Wizard Modal */}
      <AllocationWizard isOpen={isWizardOpen} onClose={() => setIsWizardOpen(false)} />

      {/* Settings Modal */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
};

export default App;
