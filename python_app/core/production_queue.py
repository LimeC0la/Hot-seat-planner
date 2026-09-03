from typing import List, Optional
from .models import ProductionTask, Machine

class ProductionQueue:
    """Manages the queue of production tasks and workload balancing."""

    def __init__(self):
        self.tasks: List[ProductionTask] = []

    def add_task(self, task: ProductionTask):
        self.tasks.append(task)
        self.reorder()

    def remove_task(self, task_id: str):
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def reorder(self):
        """Sort tasks by priority descending."""
        self.tasks.sort(key=lambda t: t.priority, reverse=True)

    def get_next_task(self, machine_type: str) -> Optional[ProductionTask]:
        """Get the next pending task for a given machine type."""
        for task in self.tasks:
            if task.status == 'pending' and task.machineType == machine_type:
                return task
        return None

    def estimate_setup_time(self, task: ProductionTask, machine: Machine) -> int:
        """Estimate the sequence-dependent setup time when switching contexts."""
        # Simple model: return defined setup time
        return task.setupTimeFromPrevious
