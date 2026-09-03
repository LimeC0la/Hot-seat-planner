import assert from 'node:assert';
import { ReliefPlanner, getShiftBounds } from '../src/core/planner.ts';

console.log('--- Running ReliefPlanner Algorithm Verification ---');

// Mock state
const mockState = {
  schemaVersion: 3,
  operators: [
    { id: 'Op1', name: 'Op1', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT1' },
    { id: 'Op2', name: 'Op2', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT2' },
    { id: 'Op3', name: 'Op3', qualifications: ['Truck'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'DT3' },
    { id: 'Relief1', name: 'Relief1', qualifications: ['Truck'], status: 'standby', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: null }
  ],
  machines: [
    { id: 'DT1', name: 'DT1', type: 'Truck', zoneId: 'Pit', transitTimeMinutes: 0, currentOperatorId: 'Op1', status: 'operational', priority: 2 },
    { id: 'DT2', name: 'DT2', type: 'Truck', zoneId: 'Pit', transitTimeMinutes: 0, currentOperatorId: 'Op2', status: 'operational', priority: 2 },
    { id: 'DT3', name: 'DT3', type: 'Truck', zoneId: 'Pit', transitTimeMinutes: 0, currentOperatorId: 'Op3', status: 'operational', priority: 2 }
  ],
  zones: [],
  zoneConnections: [],
  circuits: [],
  assignments: [],
  breaks: [],
  plannedSegments: [],
  settings: {
    durationTimingBuffer: 15,
    paddingMinutes: 5,
    defaultOperatingTimeMinutes: 120,
    breakDurationMinutes: 30,
    breakCooldownMinutes: 90,
    shiftBreakWindowStartOffsetMinutes: 120,
    shiftBreakWindowEndOffsetMinutes: 60,
    targetBreaksPerShift: 2,
    preferEvenWorkTime: true,
    autoPlanEnabled: true,
    maxWorkstretchMinutes: 240,
    handoverDurationMinutes: 5
  },
  simulatedTime: ''
};

// Test 1: Shift Bounds Calculation
const dayTestDate = new Date(2026, 7, 28, 10, 0, 0); // 10:00 AM
const bounds = getShiftBounds(dayTestDate);
assert.strictEqual(bounds.isDayShift, true, 'Should detect Day Shift');
assert.strictEqual(bounds.shiftStart.getHours(), 7, 'Shift start should be 07:00');
assert.strictEqual(bounds.shiftEnd.getHours(), 19, 'Shift end should be 19:00');
console.log('✓ Shift bounds calculation verified.');

// Test 2: Staggered mode with 1 relief spare
const plannerStaggered = new ReliefPlanner(mockState);
const planWithSpare = plannerStaggered.generatePlan(new Date(2026, 7, 28, 7, 0, 0));
assert.ok(planWithSpare.length > 0, 'Plan should have segments generated');

const breakSegs = planWithSpare.filter(s => s.segmentType === 'break');
assert.ok(breakSegs.length > 0, 'Should have planned breaks');

const reliefSegs = planWithSpare.filter(s => s.operatorName === 'Relief1' && s.segmentType === 'assignment');
assert.ok(reliefSegs.length > 0, 'Relief operator should have coverage assignments');
console.log(`✓ Staggered relief verified (${breakSegs.length} breaks, ${reliefSegs.length} relief segments).`);

// Test 3: Synchronized mode with 0 relief spares
const zeroSpareState = {
  ...mockState,
  operators: mockState.operators.filter(o => o.name !== 'Relief1')
};
const plannerSync = new ReliefPlanner(zeroSpareState);
const planSync = plannerSync.generatePlan(new Date(2026, 7, 28, 7, 0, 0));
const syncBreaks = planSync.filter(s => s.segmentType === 'break');

// In sync mode, all 3 operators break at same timestamps
const breakStarts = new Set(syncBreaks.map(s => s.startTime));
assert.strictEqual(breakStarts.size, mockState.settings.targetBreaksPerShift, 'Breaks should align into exact synchronized rounds');
console.log(`✓ Synchronized crib shutdown verified (${breakStarts.size} synchronized rounds for all operators).`);

console.log('All algorithm tests passed successfully!');
