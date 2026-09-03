import assert from 'node:assert';
import { ReliefPlanner } from '../src/core/planner.ts';

console.log('--- Running Nested Operational Grouping Verification Tests ---');

// 1. Base Setup with 2 Circuits in Zone "CN5", 1 Pit Dozer, 1 Dump Dozer, 1 Water Cart, 1 Grader
const baseState = {
  schemaVersion: 3,
  operators: [
    { id: 'DiggerOp1', name: 'DiggerOp1', qualifications: ['Digger'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'EX1' },
    { id: 'TruckOp1', name: 'TruckOp1', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT1' },
    { id: 'TruckOp2', name: 'TruckOp2', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT2' },

    { id: 'DiggerOp2', name: 'DiggerOp2', qualifications: ['Digger'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'EX2' },
    { id: 'TruckOp3', name: 'TruckOp3', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT3' },
    { id: 'TruckOp4', name: 'TruckOp4', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT4' },

    { id: 'PitDozerOp', name: 'PitDozerOp', qualifications: ['Dozer'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DZ1' },
    { id: 'DumpDozerOp', name: 'DumpDozerOp', qualifications: ['Dozer'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DZ2' },

    { id: 'WaterOp', name: 'WaterOp', qualifications: ['Water Cart'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'WC1' },
    { id: 'GraderOp', name: 'GraderOp', qualifications: ['Grader'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'GD1' }
  ],
  machines: [
    { id: 'EX1', name: 'EX1', type: 'Digger', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'DiggerOp1', status: 'operational', priority: 1 },
    { id: 'DT1', name: 'DT1', type: 'Truck', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'TruckOp1', status: 'operational', priority: 3 },
    { id: 'DT2', name: 'DT2', type: 'Truck', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'TruckOp2', status: 'operational', priority: 3 },

    { id: 'EX2', name: 'EX2', type: 'Digger', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'DiggerOp2', status: 'operational', priority: 1 },
    { id: 'DT3', name: 'DT3', type: 'Truck', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'TruckOp3', status: 'operational', priority: 3 },
    { id: 'DT4', name: 'DT4', type: 'Truck', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'TruckOp4', status: 'operational', priority: 3 },

    { id: 'DZ1', name: 'DZ1', type: 'Dozer', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'PitDozerOp', status: 'operational', priority: 3, dozerRole: 'pit' },
    { id: 'DZ2', name: 'DZ2', type: 'Dozer', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'DumpDozerOp', status: 'operational', priority: 3, dozerRole: 'dump' },

    { id: 'WC1', name: 'WC1', type: 'Water Cart', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'WaterOp', status: 'operational', priority: 3 },
    { id: 'GD1', name: 'GD1', type: 'Grader', zoneId: 'CN5', transitTimeMinutes: 0, currentOperatorId: 'GraderOp', status: 'operational', priority: 3 }
  ],
  zones: [{ id: 'CN5', name: 'CN5' }],
  zoneConnections: [],
  circuits: [
    {
      id: 'Circuit-EX1',
      name: 'EX1 Circuit',
      zoneId: 'CN5',
      diggerId: 'EX1',
      truckIds: ['DT1', 'DT2'],
      dozerId: 'DZ1',
      optimalTruckCount: 2
    },
    {
      id: 'Circuit-EX2',
      name: 'EX2 Circuit',
      zoneId: 'CN5',
      diggerId: 'EX2',
      truckIds: ['DT3', 'DT4'],
      dozerId: 'DZ1',
      optimalTruckCount: 2
    }
  ],
  assignments: [],
  breaks: [],
  plannedSegments: [],
  manualReliefs: [],
  areaShutdownConfigs: {
    CN5: { zoneId: 'CN5', mode: 'staggered', staggerMinutes: 30 }
  },
  settings: {
    durationTimingBuffer: 15,
    paddingMinutes: 5,
    defaultOperatingTimeMinutes: 120,
    breakDurationMinutes: 30,
    breakCooldownMinutes: 90,
    shiftBreakWindowStartOffsetMinutes: 120,
    shiftBreakWindowEndOffsetMinutes: 60,
    targetBreaksPerShift: 1,
    preferEvenWorkTime: true,
    autoPlanEnabled: true,
    maxWorkstretchMinutes: 240,
    handoverDurationMinutes: 5
  },
  simulatedTime: ''
};

// ── TEST 1: Circuit Simultaneous Parking (0 spares) ─────────────────────────
console.log('Test 1: Circuit Simultaneous Parking with 0 relief floaters');
const shiftStart = new Date(2026, 7, 28, 7, 0, 0);
const planner1 = new ReliefPlanner(baseState);
const plan1 = planner1.generatePlan(shiftStart);

// Circuit 1 (EX1, DT1, DT2) breaks
const ex1Break = plan1.find(s => s.operatorName === 'DiggerOp1' && s.segmentType === 'break');
const dt1Break = plan1.find(s => s.operatorName === 'TruckOp1' && s.segmentType === 'break');
const dt2Break = plan1.find(s => s.operatorName === 'TruckOp2' && s.segmentType === 'break');

assert.ok(ex1Break, 'DiggerOp1 should have a scheduled break');
assert.ok(dt1Break, 'TruckOp1 should have a scheduled break');
assert.ok(dt2Break, 'TruckOp2 should have a scheduled break');

assert.strictEqual(ex1Break.startTime, dt1Break.startTime, 'DT1 must park at the exact same minute as EX1');
assert.strictEqual(ex1Break.startTime, dt2Break.startTime, 'DT2 must park at the exact same minute as EX1');
assert.strictEqual(ex1Break.isCircuitCrib, true, 'EX1 break should be flagged as isCircuitCrib');
assert.strictEqual(dt1Break.isCircuitCrib, true, 'DT1 break should be flagged as isCircuitCrib');

console.log('✓ Inner Core: Digger and assigned haul fleet park simultaneously during crib.');

// ── TEST 2: Staggered vs Simultaneous Area Shutdown Mode ────────────────────
console.log('Test 2: Staggered vs Simultaneous Area Shutdown Modes');

// In baseState, CN5 mode is 'staggered' (30 min offset)
const ex2Break = plan1.find(s => s.operatorName === 'DiggerOp2' && s.segmentType === 'break');
assert.ok(ex2Break, 'DiggerOp2 should have a scheduled break');

const ex1Time = new Date(ex1Break.startTime).getTime();
const ex2Time = new Date(ex2Break.startTime).getTime();
const diffMinutes = Math.round((ex2Time - ex1Time) / (60 * 1000));
assert.strictEqual(diffMinutes, 30, 'Circuit 2 should be staggered by 30 minutes after Circuit 1');
console.log('✓ Area Mode "staggered": Circuit 2 crib is offset by 30 minutes.');

// Now change area mode to 'simultaneous'
const simAreaState = {
  ...baseState,
  areaShutdownConfigs: {
    CN5: { zoneId: 'CN5', mode: 'simultaneous', staggerMinutes: 30 }
  }
};
const plannerSim = new ReliefPlanner(simAreaState);
const planSim = plannerSim.generatePlan(shiftStart);

const ex1SimBreak = planSim.find(s => s.operatorName === 'DiggerOp1' && s.segmentType === 'break');
const ex2SimBreak = planSim.find(s => s.operatorName === 'DiggerOp2' && s.segmentType === 'break');
assert.strictEqual(ex1SimBreak.startTime, ex2SimBreak.startTime, 'Under Full Area Shutdown, both circuits park at the exact same time');
console.log('✓ Area Mode "simultaneous": All circuits in area park at the exact same time.');

// ── TEST 3: Dozer Functions (Pit Dozer LV link & Dump Dozer) ───────────────
console.log('Test 3: Dozer Function Specialization (Pit Dozer LV Link)');
const pitDozerBreak = plan1.find(s => s.operatorName === 'PitDozerOp' && s.segmentType === 'break');
assert.ok(pitDozerBreak, 'Pit Dozer should have a break');

// Pit Dozer in CN5 should align with the local digger (EX1) crib window to share LV transit
assert.strictEqual(pitDozerBreak.startTime, ex1Break.startTime, 'Pit Dozer aligns with digger crib to share LV to crib hut');
console.log('✓ Middle Shell: Pit Dozer aligns crib with local digger to share LV transit.');

// ── TEST 4: Manual Hotseat Preassignment Lock ──────────────────────────────
console.log('Test 4: Supervisor Preassigned Hotseat Lock');
const manualLockState = {
  ...baseState,
  operators: [
    ...baseState.operators,
    { id: 'ReliefDan', name: 'ReliefDan', qualifications: ['Digger', 'Truck'], status: 'standby', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: null }
  ],
  manualReliefs: [
    {
      id: 'lock_1',
      machineName: 'EX1',
      reliefOperatorName: 'ReliefDan',
      startTime: new Date(2026, 7, 28, 10, 30, 0).toISOString(),
      endTime: new Date(2026, 7, 28, 11, 0, 0).toISOString(),
      locked: true
    }
  ]
};

const plannerLock = new ReliefPlanner(manualLockState);
const planLock = plannerLock.generatePlan(shiftStart);

const lockedReliefSeg = planLock.find(
  s => s.machineName === 'EX1' && s.operatorName === 'ReliefDan' && s.segmentType === 'assignment'
);
assert.ok(lockedReliefSeg, 'EX1 must have ReliefDan assigned at locked time');
assert.strictEqual(lockedReliefSeg.isHotseatRelief, true, 'Relief segment flagged as isHotseatRelief');

const lockedStart = new Date(lockedReliefSeg.startTime);
assert.strictEqual(lockedStart.getHours(), 10, 'Locked start hour should be 10:30');
assert.strictEqual(lockedStart.getMinutes(), 30, 'Locked start min should be 30');
console.log('✓ Manual Preassigned Hotseat Lock strictly honored on EX1 with ReliefDan.');

console.log('🎉 ALL NESTED OPERATIONAL GROUPING TESTS PASSED SUCCESSFULLY!');
