import { AppState } from '../types';

export const fetchState = async (): Promise<AppState> => {
  const res = await fetch('/api/state');
  if (!res.ok) throw new Error('Failed to fetch state');
  return res.json();
};

export const assignOperator = async (operatorId: string, machineId: string): Promise<AppState> => {
  const res = await fetch('/api/assign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operatorId, machineId }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Assignment failed');
  }
  const data = await res.json();
  return data.state;
};

export const sendOnBreak = async (operatorId: string): Promise<{ state: AppState, travelTime: number }> => {
  const res = await fetch('/api/break', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operatorId }),
  });
  if (!res.ok) throw new Error('Break assignment failed');
  return res.json();
};

export const toggleBlast = async (zoneId: string, active: boolean): Promise<AppState> => {
  const res = await fetch('/api/blast', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ zoneId, active }),
  });
  if (!res.ok) throw new Error('Blast toggle failed');
  const data = await res.json();
  return data.state;
};

export const addOperator = async (name: string, qualifications: string[]): Promise<AppState> => {
  const res = await fetch('/api/operators', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, qualifications }),
  });
  if (!res.ok) throw new Error('Failed to add operator');
  const data = await res.json();
  return data.state;
};

export const deleteOperator = async (id: string): Promise<AppState> => {
  const res = await fetch(`/api/operators/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete operator');
  const data = await res.json();
  return data.state;
};

export const addMachine = async (name: string, type: string, zoneId: string, transitTimeMinutes: number): Promise<AppState> => {
  const res = await fetch('/api/machines', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, type, zoneId, transitTimeMinutes }),
  });
  if (!res.ok) throw new Error('Failed to add machine');
  const data = await res.json();
  return data.state;
};

export const deleteMachine = async (id: string): Promise<AppState> => {
  const res = await fetch(`/api/machines/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete machine');
  const data = await res.json();
  return data.state;
};

export const addZone = async (name: string): Promise<AppState> => {
  const res = await fetch('/api/zones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to add zone');
  const data = await res.json();
  return data.state;
};

export const deleteZone = async (id: string): Promise<AppState> => {
  const res = await fetch(`/api/zones/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete zone');
  const data = await res.json();
  return data.state;
};
