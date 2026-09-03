import assert from 'node:assert';

console.log('--- Running Relief Swap & Primary Handback Logic Verification ---');

// Mock machine and operators
const machine = {
  id: 'DT244',
  name: 'DT244',
  type: 'Truck',
  zoneId: 'IM9',
  transitTimeMinutes: 0,
  currentOperatorId: 'Tina S.',
  primaryOperatorId: 'Tina S.',
  reliefOperatorId: null,
  status: 'operational',
  priority: 2
};

const operators = [
  { id: 'op1', name: 'Tina S.', qualifications: ['Truck'], status: 'working', breaksTaken: 0 },
  { id: 'op2', name: 'Daniel T.', qualifications: ['Truck'], status: 'standby', breaksTaken: 0 },
  { id: 'op3', name: 'Trey C.', qualifications: ['Truck'], status: 'standby', breaksTaken: 0 }
];

// Helper: Calculate relief state
function getReliefState(m, plannedReliefOp, now) {
  const isCurrentlyRelieved = Boolean(
    m.reliefOperatorId && m.currentOperatorId === m.reliefOperatorId
  );

  if (isCurrentlyRelieved) {
    return {
      isCurrentlyRelieved: true,
      pendingRelief: null,
      returnPrimary: m.primaryOperatorId || null
    };
  }

  return {
    isCurrentlyRelieved: false,
    pendingRelief: plannedReliefOp || null,
    returnPrimary: null
  };
}

// 1. Initial State: Tina S. is driving. Daniel T. is scheduled to relieve at 10:00.
let state = getReliefState(machine, 'Daniel T.', new Date());
assert.strictEqual(state.isCurrentlyRelieved, false);
assert.strictEqual(state.pendingRelief, 'Daniel T.');
assert.strictEqual(state.returnPrimary, null);
console.log('✓ Step 1: Planned relief prompt appears for Daniel T.');

// 2. Supervisor hits "Relieve: Daniel T."
// Simulate relieveOperatorOnMachine
machine.reliefOperatorId = 'Daniel T.';
machine.currentOperatorId = 'Daniel T.';
machine.primaryOperatorId = 'Tina S.';
operators.find(o => o.name === 'Tina S.').status = 'on_break';
operators.find(o => o.name === 'Daniel T.').status = 'working';

// 3. Immediately evaluate relief state after swap
state = getReliefState(machine, 'Trey C.', new Date());

// VERIFY: The button does NOT change to Trey C.!
assert.strictEqual(state.isCurrentlyRelieved, true, 'Machine must be recognized as currently under active relief');
assert.strictEqual(state.pendingRelief, null, 'Must NOT prompt to relieve Daniel T. with the next operator!');
assert.strictEqual(state.returnPrimary, 'Tina S.', 'Must offer Return action for primary operator Tina S.');
console.log('✓ Step 2: After hitting relieve, Daniel T. is active in cab, no secondary relief prompt is shown.');

// 4. Return primary driver (break finishes or supervisor clicks Return)
machine.currentOperatorId = machine.primaryOperatorId;
machine.reliefOperatorId = null;
operators.find(o => o.name === 'Tina S.').status = 'working';
operators.find(o => o.name === 'Daniel T.').status = 'standby';

state = getReliefState(machine, null, new Date());
assert.strictEqual(state.isCurrentlyRelieved, false);
assert.strictEqual(machine.currentOperatorId, 'Tina S.');
assert.strictEqual(state.returnPrimary, null);
assert.strictEqual(state.pendingRelief, null);
console.log('✓ Step 3: Primary driver Tina S. returned to cab, Daniel T. returned to standby.');

console.log('🎉 RELIEF SWAP & RETURN VERIFICATION PASSED!');
