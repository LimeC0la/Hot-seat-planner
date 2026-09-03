import React, { useState } from 'react';
import { useShiftStore } from '../core/store';
import { TimelineRuler } from './TimelineRuler';
import { TimelineTrack } from './TimelineTrack';
import { MachineContextMenu } from './MachineContextMenu';
import { MachineDetailModal } from './MachineDetailModal';
import { PreassignHotseatModal } from './PreassignHotseatModal';
import { formatShortName } from '../core/planner';
import { Machine, Circuit } from '../core/types';

export const ZoneView: React.FC = () => {
  const {
    appState,
    currentTime,
    relieveOperatorOnMachine,
    returnPrimaryOperator,
    setAreaShutdownMode,
    adjustCircuitCapacity
  } = useShiftStore();

  const now = new Date(currentTime);
  const zones = appState.zones;
  const machines = appState.machines;
  const operators = appState.operators;
  const circuits = appState.circuits;
  const plannedSegments = appState.plannedSegments;
  const areaConfigs = appState.areaShutdownConfigs || {};

  // Interactive modal/menu states
  const [contextMenu, setContextMenu] = useState<{
    machine: Machine;
    circuit?: Circuit | null;
    position: { x: number; y: number };
  } | null>(null);

  const [detailMachine, setDetailMachine] = useState<Machine | null>(null);
  const [preassignMachine, setPreassignMachine] = useState<Machine | null>(null);

  const getMachineSegments = (machineName: string) => {
    return plannedSegments.filter(s => s.machineName === machineName);
  };

  const getReliefState = (m: Machine) => {
    // 1. Check if currently under active relief
    const isCurrentlyRelieved = Boolean(
      m.reliefOperatorId && m.currentOperatorId === m.reliefOperatorId
    );

    if (isCurrentlyRelieved) {
      return {
        isCurrentlyRelieved: true,
        primaryOpName: m.primaryOperatorId || null,
        reliefOpName: m.reliefOperatorId || null,
        pendingRelief: null,
        returnPrimary: m.primaryOperatorId || null
      };
    }

    // 2. Machine is operating with primary driver.
    // Check if there is a scheduled hotseat relief starting around now!
    const segs = getMachineSegments(m.name);
    const scheduled = segs.find(s => {
      if (s.segmentType !== 'assignment') return false;
      if (!s.isHotseatRelief) return false;
      if (s.operatorName === m.currentOperatorId) return false;

      const sStart = new Date(s.startTime);
      const sEnd = new Date(s.endTime);
      return now >= new Date(sStart.getTime() - 10 * 60 * 1000) && now <= sEnd;
    });

    let pendingRelief: string | null = null;
    if (scheduled) {
      const op = operators.find(o => o.name === scheduled.operatorName);
      if (op && (op.status === 'standby' || op.status === 'working')) {
        pendingRelief = scheduled.operatorName;
      }
    }

    return {
      isCurrentlyRelieved: false,
      primaryOpName: m.primaryOperatorId || m.currentOperatorId || null,
      reliefOpName: null,
      pendingRelief,
      returnPrimary: null
    };
  };

  const handleOpenContextMenu = (
    e: React.MouseEvent,
    machine: Machine,
    circuit?: Circuit | null
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      machine,
      circuit,
      position: { x: e.clientX, y: e.clientY }
    });
  };

  // Helper to render a machine row
  const renderMachineRow = (
    m: Machine,
    circuit?: Circuit | null,
    isIndented = false
  ) => {
    const isNR = m.status === 'not_required';
    const isMaint = m.status === 'maintenance';
    const currentOp = operators.find(o => o.name === m.currentOperatorId);
    const { isCurrentlyRelieved, primaryOpName, reliefOpName, pendingRelief, returnPrimary } = getReliefState(m);
    const segs = getMachineSegments(m.name);
    const hasLock = (appState.manualReliefs || []).some(
      l => l.machineName === m.name && l.locked
    );

    return (
      <div
        key={m.id}
        onContextMenu={e => handleOpenContextMenu(e, m, circuit)}
        onClick={() => setDetailMachine(m)}
        className={`group flex items-center gap-3 p-2 rounded-xl border transition-all cursor-pointer select-none ${
          isIndented ? 'ml-5 bg-slate-900/90 border-slate-800 hover:border-slate-655' : ''
        } ${
          isNR
            ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
            : isMaint
            ? 'bg-amber-950/20 border-amber-900/40'
            : 'bg-slate-850 border-slate-750 hover:border-sky-600/70 hover:shadow-md'
        }`}
      >
        {/* Machine Label & Driver Info */}
        <div className="w-56 shrink-0 flex items-center justify-between pr-2">
          <div className="min-w-0 pr-1">
            <div className="flex items-center gap-1.5 truncate">
              {isIndented && <span className="text-slate-600 text-xs">↳</span>}
              <span className="text-sm font-bold text-slate-100">{m.name}</span>
              <span className="text-[10px] px-1 py-0.2 bg-slate-800 text-slate-400 rounded">
                {m.type}
              </span>
              {m.dozerRole && (
                <span
                  className={`text-[9px] px-1 py-0.2 rounded font-semibold ${
                    m.dozerRole === 'pit'
                      ? 'bg-sky-950 text-sky-400 border border-sky-800/50'
                      : 'bg-amber-950 text-amber-400 border border-amber-800/50'
                  }`}
                  title={
                    m.dozerRole === 'pit'
                      ? 'Pit Dozer: Aligns with digger to share LV transit to crib'
                      : 'Dump Dozer: Tip head safety; continuous operation while haulage runs'
                  }
                >
                  {m.dozerRole === 'pit' ? 'Pit (LV)' : 'Dump'}
                </span>
              )}
              {hasLock && (
                <span className="text-[10px]" title="Manual Hotseat Locked">
                  🔒
                </span>
              )}
            </div>

            <div className="text-xs text-slate-400 truncate flex items-center gap-1 mt-0.5">
              {isCurrentlyRelieved && reliefOpName ? (
                <span
                  className="text-emerald-300 font-semibold truncate"
                  title={`Relieved by ${reliefOpName} (Primary: ${primaryOpName || 'Driver'})`}
                >
                  ⚡ {formatShortName(reliefOpName)}{' '}
                  <span className="text-[10px] text-slate-400 font-normal">
                    ({formatShortName(primaryOpName || '')} on crib)
                  </span>
                </span>
              ) : currentOp ? (
                <span className="text-sky-300 font-medium truncate">
                  👷 {formatShortName(currentOp.name)}
                </span>
              ) : isNR ? (
                <span className="text-slate-500 italic text-[11px]">Parked</span>
              ) : (
                <span className="text-rose-400 italic text-[11px]">Uncrewed</span>
              )}
            </div>
          </div>

          {/* Quick 3-dot Action Menu button for touch */}
          <button
            onClick={e => handleOpenContextMenu(e, m, circuit)}
            className="w-7 h-7 rounded-lg hover:bg-slate-750 text-slate-400 hover:text-slate-200 flex items-center justify-center font-bold text-sm shrink-0 transition-colors"
            title="Open Machine Options (or Right-Click)"
          >
            ⋮
          </button>
        </div>

        {/* Timeline Track */}
        <div className="flex-1 min-w-0">
          <TimelineTrack
            segments={segs}
            currentTime={now}
            pendingReliefName={pendingRelief}
            onConfirmRelief={() => {
              if (pendingRelief) relieveOperatorOnMachine(m.name, pendingRelief);
            }}
            returnPrimaryName={returnPrimary}
            onConfirmReturnPrimary={() => {
              returnPrimaryOperator(m.name);
            }}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {zones.map(zone => {
        const zoneMachines = machines.filter(
          m => m.zoneId === zone.name || m.zoneId === zone.id
        );
        const zoneCircuits = circuits.filter(c => c.zoneId === zone.name || c.zoneId === zone.id);

        // Classify machines into shells
        const pitServiceMachines = zoneMachines.filter(
          m => m.type.toLowerCase().includes('grader') || m.type.toLowerCase().includes('water')
        );

        const benchSupportMachines = zoneMachines.filter(
          m =>
            m.type.toLowerCase().includes('dozer') ||
            m.type.toLowerCase().includes('rom loader') ||
            (m.type.toLowerCase().includes('loader') && !zoneCircuits.some(c => c.diggerId === m.name))
        );

        const circuitMachineNames = new Set<string>();
        zoneCircuits.forEach(c => {
          circuitMachineNames.add(c.diggerId);
          circuitMachineNames.add(c.id);
          c.truckIds.forEach(t => circuitMachineNames.add(t));
        });

        const unassignedZoneMachines = zoneMachines.filter(
          m =>
            !circuitMachineNames.has(m.name) &&
            !pitServiceMachines.some(p => p.id === m.id) &&
            !benchSupportMachines.some(b => b.id === m.id)
        );

        const currentAreaConfig = areaConfigs[zone.name] || {
          zoneId: zone.name,
          mode: 'staggered',
          staggerMinutes: 30
        };

        const isSimultaneous = currentAreaConfig.mode === 'simultaneous';

        return (
          <div
            key={zone.id}
            className="bg-slate-900 border border-slate-800 rounded-2xl shadow-lg overflow-hidden"
          >
            {/* Zone Header with Dispatch Shutdown Toggle */}
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-xl">📍</span>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-slate-100 tracking-wide">
                      {zone.name}
                    </h2>
                    <span className="px-2 py-0.5 text-xs font-semibold bg-slate-800 text-slate-400 rounded-full border border-slate-700">
                      {zoneMachines.length} units
                    </span>
                    {zone.hasActiveBlast && (
                      <span className="px-2 py-0.5 text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded animate-pulse">
                        ⚠️ Blast Exclusion
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400">
                    {zoneCircuits.length} Production Circuit{zoneCircuits.length === 1 ? '' : 's'} •{' '}
                    {benchSupportMachines.length} Support Dozers • {pitServiceMachines.length} Pit Services
                  </p>
                </div>
              </div>

              {/* Live Dispatch Area Shutdown Selector */}
              <div className="flex items-center gap-2 bg-slate-900/90 p-1 rounded-xl border border-slate-750 text-xs">
                <span className="text-[11px] font-bold text-slate-400 px-2 uppercase tracking-wider">
                  Crib Mode:
                </span>
                <button
                  onClick={() => setAreaShutdownMode(zone.name, 'simultaneous')}
                  className={`px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                    isSimultaneous
                      ? 'bg-amber-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                  title="All circuits and tethered fleets in this pit sector park at the exact same minute"
                >
                  <span>⚡</span>
                  <span>Full Area Shutdown</span>
                </button>
                <button
                  onClick={() => setAreaShutdownMode(zone.name, 'staggered', 30)}
                  className={`px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                    !isSimultaneous
                      ? 'bg-sky-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                  title="Circuits stagger their crib park-ups by 30 minutes to reduce crib room congestion"
                >
                  <span>🕒</span>
                  <span>Staggered (30m)</span>
                </button>
              </div>
            </div>

            {/* Zone Body */}
            <div className="p-4 space-y-4">
              {/* Shared Ruler Header */}
              <div className="flex items-center gap-3 px-2">
                <div className="w-56 shrink-0 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                  Concentric Operational Shells
                </div>
                <div className="flex-1">
                  <TimelineRuler currentTime={now} />
                </div>
              </div>

              {zoneMachines.length === 0 && (
                <div className="py-8 text-center text-sm text-slate-500 italic bg-slate-950/30 rounded-xl border border-dashed border-slate-800">
                  No equipment allocated to {zone.name}
                </div>
              )}

              {/* ─────────────────────────────────────────────────────────── */}
              {/* SHELL 3: PIT SERVICES (Water Carts & Graders)              */}
              {/* ─────────────────────────────────────────────────────────── */}
              {pitServiceMachines.length > 0 && (
                <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 px-1">
                    <span className="flex items-center gap-1.5 text-sky-400">
                      <span>🛠️</span>
                      <span>Shell 3: Pit Services & Road Maintenance</span>
                    </span>
                    <span className="text-[11px] font-semibold text-slate-500">
                      Independent / Decoupled
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {pitServiceMachines.map(m => renderMachineRow(m))}
                  </div>
                </div>
              )}

              {/* ─────────────────────────────────────────────────────────── */}
              {/* SHELL 2: BENCH & DUMP SUPPORT (Dozers & Loaders)           */}
              {/* ─────────────────────────────────────────────────────────── */}
              {benchSupportMachines.length > 0 && (
                <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400 px-1">
                    <span className="flex items-center gap-1.5 text-amber-400">
                      <span>🏗️</span>
                      <span>Shell 2: Bench & Dump Support (Dozers)</span>
                    </span>
                    <span className="text-[11px] font-semibold text-slate-500">
                      Semi-Independent • LV Linked / Continuous Tip
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {benchSupportMachines.map(m => renderMachineRow(m))}
                  </div>
                </div>
              )}

              {/* ─────────────────────────────────────────────────────────── */}
              {/* SHELL 1: DIRECT PRODUCTION CIRCUITS (Digger + Haul Trucks) */}
              {/* ─────────────────────────────────────────────────────────── */}
              {zoneCircuits.length > 0 && (
                <div className="space-y-3">
                  <div className="text-xs font-bold text-slate-400 px-1 flex items-center gap-1.5 text-emerald-400">
                    <span>⛏️</span>
                    <span>Shell 1: Direct Production Circuits (Tightly Coupled)</span>
                  </div>

                  {zoneCircuits.map(circuit => {
                    const digger = machines.find(
                      m => m.name === circuit.diggerId || m.name === circuit.id
                    );
                    const circuitTrucks = machines.filter(m => circuit.truckIds.includes(m.name));

                    // Evaluate if circuit is hot-seating or in synchronized crib
                    const diggerSegs = digger ? getMachineSegments(digger.name) : [];
                    const hasHotseat = diggerSegs.some(s => s.isHotseatRelief);
                    const hasCribPark = diggerSegs.some(s => s.isCircuitCrib);

                    return (
                      <div
                        key={circuit.id}
                        className="bg-slate-950/60 rounded-xl p-3 border border-slate-800/90 space-y-2.5 shadow-sm"
                      >
                        {/* Circuit Sub-Header */}
                        <div className="flex items-center justify-between px-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-100">
                              Circuit: {circuit.name}
                            </span>
                            <span className="text-xs text-slate-400">
                              ({circuitTrucks.length} Trucks assigned)
                            </span>
                            {hasHotseat ? (
                              <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 rounded-full flex items-center gap-1">
                                <span>⚡</span> Hot-Seating Active
                              </span>
                            ) : hasCribPark ? (
                              <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-950/80 text-amber-300 border border-amber-700/60 rounded-full flex items-center gap-1">
                                <span>🛑</span> Synchronized Circuit Crib
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 text-[10px] font-semibold bg-slate-800 text-slate-400 rounded-full">
                                Scheduled
                              </span>
                            )}
                          </div>

                          {/* Circuit Capacity Adjuster */}
                          <div className="flex items-center gap-1 text-xs">
                            <span className="text-slate-400 text-[11px] mr-1">Target Fleet:</span>
                            <button
                              onClick={() => adjustCircuitCapacity(circuit.id, -1)}
                              className="w-6 h-6 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center justify-center text-xs"
                              title="Decrease target truck count"
                            >
                              -
                            </button>
                            <span className="font-bold text-sky-400 px-1 text-xs">
                              {circuit.optimalTruckCount || 4}
                            </span>
                            <button
                              onClick={() => adjustCircuitCapacity(circuit.id, 1)}
                              className="w-6 h-6 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center justify-center text-xs"
                              title="Increase target truck count"
                            >
                              +
                            </button>
                          </div>
                        </div>

                        {/* Digger (Leader) */}
                        {digger ? (
                          renderMachineRow(digger, circuit, false)
                        ) : (
                          <div className="text-xs text-rose-400 italic p-2 bg-rose-950/20 rounded-lg">
                            Digger ({circuit.diggerId}) missing or not configured
                          </div>
                        )}

                        {/* Tethered Haul Fleet (Followers) */}
                        {circuitTrucks.length > 0 ? (
                          <div className="space-y-1.5">
                            {circuitTrucks.map(truck => renderMachineRow(truck, circuit, true))}
                          </div>
                        ) : (
                          <div className="ml-5 text-xs text-slate-500 italic p-2 bg-slate-900/40 rounded-lg border border-dashed border-slate-800">
                            No haul trucks tethered to this circuit.
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Other Unassigned Machines in Zone */}
              {unassignedZoneMachines.length > 0 && (
                <div className="bg-slate-950/30 rounded-xl p-3 border border-dashed border-slate-800 space-y-2">
                  <div className="text-xs font-semibold text-slate-400 px-1">
                    Unassigned Equipment in {zone.name}
                  </div>
                  <div className="space-y-1.5">
                    {unassignedZoneMachines.map(m => renderMachineRow(m))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* Context Menu on Right Click or Touch */}
      {contextMenu && (
        <MachineContextMenu
          machine={contextMenu.machine}
          circuit={contextMenu.circuit}
          position={contextMenu.position}
          onClose={() => setContextMenu(null)}
          onOpenDetail={m => setDetailMachine(m)}
          onOpenPreassign={m => setPreassignMachine(m)}
        />
      )}

      {/* Full Machine Inspector Modal on Click */}
      {detailMachine && (
        <MachineDetailModal
          machine={detailMachine}
          circuit={circuits.find(
            c => c.diggerId === detailMachine.name || c.truckIds.includes(detailMachine.name)
          )}
          isOpen={Boolean(detailMachine)}
          onClose={() => setDetailMachine(null)}
          onOpenPreassign={m => setPreassignMachine(m)}
        />
      )}

      {/* Preassign Hotseat Dialog */}
      {preassignMachine && (
        <PreassignHotseatModal
          machine={preassignMachine}
          isOpen={Boolean(preassignMachine)}
          onClose={() => setPreassignMachine(null)}
        />
      )}
    </div>
  );
};
