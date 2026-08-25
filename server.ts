import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { AppState, Machine, Operator, Zone } from './src/types.js'; // Ensure correct extension for ESM resolution if needed

// Mock Data
let state: AppState = {
  operators: [
    { id: 'o1', name: 'Alice Smith', qualifications: ['Truck', 'Auxiliary'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'm1' },
    { id: 'o2', name: 'Bob Jones', qualifications: ['Digger', 'ROM Loader'], status: 'working', standbyTimeMinutes: 0, breaksTaken: 0, currentAssignmentId: 'm3' },
    { id: 'o3', name: 'Charlie Davis', qualifications: ['Truck', 'Digger'], status: 'standby', standbyTimeMinutes: 45, breaksTaken: 0, currentAssignmentId: null },
    { id: 'o4', name: 'Diana Prince', qualifications: ['Truck'], status: 'standby', standbyTimeMinutes: 80, breaksTaken: 0, currentAssignmentId: null },
    { id: 'o5', name: 'Evan Wright', qualifications: ['Auxiliary', 'ROM Loader'], status: 'standby', standbyTimeMinutes: 20, breaksTaken: 1, currentAssignmentId: null },
    { id: 'o6', name: 'Frank Castle', qualifications: ['Truck'], status: 'on_break', standbyTimeMinutes: 0, breaksTaken: 1, currentAssignmentId: null },
  ],
  machines: [
    { id: 'm1', name: 'DT-101', type: 'Truck', zoneId: 'z1', currentOperatorId: 'o1', status: 'operational', transitTimeMinutes: 10 },
    { id: 'm2', name: 'DT-102', type: 'Truck', zoneId: 'z1', currentOperatorId: null, status: 'operational', transitTimeMinutes: 10 },
    { id: 'm3', name: 'EX-201', type: 'Digger', zoneId: 'z2', currentOperatorId: 'o2', status: 'operational', transitTimeMinutes: 15 },
    { id: 'm4', name: 'DOZ-301', type: 'Auxiliary', zoneId: 'z2', currentOperatorId: null, status: 'operational', transitTimeMinutes: 15 },
    { id: 'm5', name: 'ROM-401', type: 'ROM Loader', zoneId: 'z3', currentOperatorId: null, status: 'operational', transitTimeMinutes: 5 },
  ],
  zones: [
    { id: 'z1', name: 'North Pit', hasActiveBlast: false },
    { id: 'z2', name: 'South Pit', hasActiveBlast: false },
    { id: 'z3', name: 'ROM Pad', hasActiveBlast: false },
  ],
  simulatedTime: new Date().toISOString(),
};

// ATB Tick Logic (Simulation)
setInterval(() => {
  state.operators.forEach(op => {
    if (op.status === 'standby') {
      op.standbyTimeMinutes += 1; // 1 min per tick for demo speed
    }
  });
}, 5000); // Every 5 seconds in real time simulates 1 minute for demo purposes

async function startServer() {
  const app = express();
  const PORT = 3000;
  
  app.use(express.json());

  // API Routes
  app.get('/api/state', (req, res) => {
    res.json(state);
  });

  app.post('/api/assign', (req, res) => {
    const { operatorId, machineId } = req.body;
    const operator = state.operators.find(o => o.id === operatorId);
    const machine = state.machines.find(m => m.id === machineId);

    if (!operator || !machine) {
      return res.status(404).json({ error: 'Operator or Machine not found' });
    }

    if (!operator.qualifications.includes(machine.type)) {
      return res.status(400).json({ error: 'Operator not qualified for this machine type.' });
    }

    // Handle existing operator on the machine (they go to standby)
    if (machine.currentOperatorId) {
      const prevOp = state.operators.find(o => o.id === machine.currentOperatorId);
      if (prevOp) {
        prevOp.status = 'standby';
        prevOp.currentAssignmentId = null;
      }
    }

    // If operator was on another machine, clear that machine
    if (operator.currentAssignmentId) {
      const prevMachine = state.machines.find(m => m.id === operator.currentAssignmentId);
      if (prevMachine) {
        prevMachine.currentOperatorId = null;
      }
    }

    operator.status = 'working';
    operator.standbyTimeMinutes = 0; // Reset ATB gauge when assigned
    operator.currentAssignmentId = machine.id;
    machine.currentOperatorId = operator.id;

    res.json({ success: true, state });
  });

  app.post('/api/break', (req, res) => {
    const { operatorId } = req.body;
    const operator = state.operators.find(o => o.id === operatorId);
    if (!operator) return res.status(404).json({ error: 'Operator not found' });

    let travelTime = 0;
    if (operator.currentAssignmentId) {
      const machine = state.machines.find(m => m.id === operator.currentAssignmentId);
      if (machine) {
        travelTime = machine.transitTimeMinutes;
        machine.currentOperatorId = null;
      }
    }

    operator.status = 'on_break';
    operator.currentAssignmentId = null;
    operator.breaksTaken += 1;
    
    // In a full implementation, a timeout would return them to 'standby' after (30 + travelTime) minutes.
    // We'll simulate this with a quick timeout for the prototype.
    setTimeout(() => {
      const op = state.operators.find(o => o.id === operatorId);
      if (op && op.status === 'on_break') {
        op.status = 'standby';
      }
    }, (30000)); // 30 seconds real time for demo purposes

    res.json({ success: true, travelTime, state });
  });

  app.post('/api/blast', (req, res) => {
    const { zoneId, active } = req.body;
    const zone = state.zones.find(z => z.id === zoneId);
    if (!zone) return res.status(404).json({ error: 'Zone not found' });

    zone.hasActiveBlast = active;

    // Handle blast exclusions - machines in this zone are blocked, operators go on paid rest.
    state.machines.forEach(m => {
      if (m.zoneId === zoneId) {
        m.status = active ? 'blast_exclusion' : 'operational';
        
        if (active && m.currentOperatorId) {
          const op = state.operators.find(o => o.id === m.currentOperatorId);
          if (op) {
            op.status = 'on_break';
            op.breaksTaken += 1; // Count as their paid rest interval
            op.currentAssignmentId = null;
            m.currentOperatorId = null;
            
            // Auto return to standby after blast or timeout
            setTimeout(() => {
               const currentOp = state.operators.find(o => o.id === op.id);
               if (currentOp && currentOp.status === 'on_break') {
                 currentOp.status = 'standby';
               }
            }, 30000);
          }
        }
      }
    });

    res.json({ success: true, state });
  });

  app.post('/api/operators', (req, res) => {
    const { name, qualifications } = req.body;
    const newOp: Operator = {
      id: `o${Date.now()}`,
      name,
      qualifications,
      status: 'standby',
      standbyTimeMinutes: 0,
      breaksTaken: 0,
      currentAssignmentId: null
    };
    state.operators.push(newOp);
    res.json({ success: true, state });
  });

  app.delete('/api/operators/:id', (req, res) => {
    const op = state.operators.find(o => o.id === req.params.id);
    if (op && op.currentAssignmentId) {
      const machine = state.machines.find(m => m.id === op.currentAssignmentId);
      if (machine) machine.currentOperatorId = null;
    }
    state.operators = state.operators.filter(o => o.id !== req.params.id);
    res.json({ success: true, state });
  });

  app.post('/api/machines', (req, res) => {
    const { name, type, zoneId, transitTimeMinutes } = req.body;
    const newMachine: Machine = {
      id: `m${Date.now()}`,
      name,
      type,
      zoneId,
      transitTimeMinutes,
      currentOperatorId: null,
      status: 'operational'
    };
    state.machines.push(newMachine);
    res.json({ success: true, state });
  });

  app.delete('/api/machines/:id', (req, res) => {
    const machine = state.machines.find(m => m.id === req.params.id);
    if (machine && machine.currentOperatorId) {
      const op = state.operators.find(o => o.id === machine.currentOperatorId);
      if (op) {
        op.status = 'standby';
        op.currentAssignmentId = null;
      }
    }
    state.machines = state.machines.filter(m => m.id !== req.params.id);
    res.json({ success: true, state });
  });

  app.post('/api/zones', (req, res) => {
    const { name } = req.body;
    const newZone: Zone = {
      id: `z${Date.now()}`,
      name,
      hasActiveBlast: false
    };
    state.zones.push(newZone);
    res.json({ success: true, state });
  });

  app.delete('/api/zones/:id', (req, res) => {
    const machinesToDelete = state.machines.filter(m => m.zoneId === req.params.id);
    machinesToDelete.forEach(m => {
       if (m.currentOperatorId) {
          const op = state.operators.find(o => o.id === m.currentOperatorId);
          if (op) {
            op.status = 'standby';
            op.currentAssignmentId = null;
          }
       }
    });
    state.machines = state.machines.filter(m => m.zoneId !== req.params.id);
    state.zones = state.zones.filter(z => z.id !== req.params.id);
    res.json({ success: true, state });
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
