"""
This module contains the scheduling algorithms used in the scheduling API.

It provides implementations for both Least Deadline First (LDF) and Earliest Deadline First (EDF) scheduling strategies, applicable in single-core and multi-core processor environments. Functions within are designed to be called with specific application and platform data structures.

Functions:
- ldf_singlecore: Schedules tasks on a single-core processor using LDF.
- edf_singlecore: Schedules tasks on a single-core processor using EDF.
- rms_singlecore: Schedules tasks on a single-core processor using RMS.
- ll_singlecore: Schedules tasks on a single-core processor using LL.
- ldf_multicore: Schedules tasks on multiple cores using LDF.
- edf_multicore: Schedules tasks on multiple cores using EDF.
"""

__author__ = "GROUP 16"
__version__ = "1.0.0"


import networkx as nx

# just an eample for the structure of the schedule to be returned and to check the frontend and backend connection
example_schedule = [
    {
        "task_id": 3,
        "node_id": 0,
        "end_time": 20,
        "deadline": 256,
        "start_time": 0,
    },
    {
        "task_id": 2,
        "node_id": 0,
        "end_time": 40,
        "deadline": 300,
        "start_time": 20,
    },
    {
        "task_id": 1,
        "node_id": 0,
        "end_time": 60,
        "deadline": 250,
        "start_time": 40,
    },
    {
        "task_id": 0,
        "node_id": 0,
        "end_time": 80,
        "deadline": 250,
        "start_time": 60,
    },
]


def build_dependency_graph(application_data):
    """Build a directed graph representing task dependencies based on messages."""
    # arlind: We use a Directed Graph (DiGraph) because dependencies only flow one way.
    # If Task A sends a message to Task B, B depends on A. The edge is A -> B.
    G = nx.DiGraph()
    
    # Add all tasks as nodes
    for task in application_data['tasks']:
        G.add_node(task['id'], **task)
  
    # Add edges based on messages (sender -> receiver dependency)
    # arlind: These edges are the physical constraints. A receiver cannot start until the sender is completely finished.
    for message in application_data['messages']:
        G.add_edge(message['sender'], message['receiver'], **message)
    
    return G


def get_ready_tasks(G, scheduled_tasks):
    """Get tasks that are ready to be scheduled (all predecessors scheduled)."""
    ready_tasks = []
    for task_id in G.nodes():
        if task_id not in scheduled_tasks:
            # arlind: A task is ONLY considered "ready" if every single one of its predecessors 
            # is already fully processed and sitting in the 'scheduled_tasks' list.
            predecessors = list(G.predecessors(task_id))
            if all(pred in scheduled_tasks for pred in predecessors):
                ready_tasks.append(task_id)
    return ready_tasks


def get_predecessor_end_time(G, task_id, schedule):
    """Get the latest end time of all predecessors for a task."""
    predecessors = list(G.predecessors(task_id))
    if not predecessors:
        return 0
    
    max_end_time = 0
    for pred_id in predecessors:
        # Find the scheduled entry for the predecessor
        pred_schedule_entry = next((item for item in schedule if item['task_id'] == pred_id), None)
        if pred_schedule_entry:
            # arlind: This is the Causality Law. If a task has 3 predecessors finishing at t=10, t=20, and t=50,
            # it MUST wait until t=50. We always take the maximum end time of all incoming data.
            max_end_time = max(max_end_time, pred_schedule_entry['end_time'])

    return max_end_time





def edf_single_node(application_data):
    """
    Schedule jobs on a single node using the Earliest Deadline First (EDF) strategy.
    This is a work-conserving (non-idling) scheduler that respects dependencies.
    """
    G = build_dependency_graph(application_data)
    schedule = []
    current_time = 0
    tasks_to_schedule = set(G.nodes())
    completion_times = {}
    missed_deadlines=[]
    while len(completion_times) < len(G.nodes()):
        # Find all tasks whose predecessors have completed
        ready_tasks = [
            t for t in tasks_to_schedule
            if all(p in completion_times for p in G.predecessors(t))
        ]

        if not ready_tasks:
            break  # No more tasks can be made ready

        # Determine the earliest time the processor could start the next task.
        # This involves checking when ready tasks are actually available.
        # arlind: IDLE TIME HANDLING. If the CPU is currently free, but no data has arrived yet, 
        # we have to figure out exactly what time the next piece of data will arrive so we can jump the clock forward.
        next_possible_start_time = float('inf')
        runnable_tasks = []
        for tid in ready_tasks:
            pred_end = max([completion_times.get(p, 0) for p in G.predecessors(tid)], default=0)
            if max(current_time, pred_end) <= current_time:
                runnable_tasks.append(tid)
            next_possible_start_time = min(next_possible_start_time, max(current_time, pred_end))
        
        # If no task can run now, advance time to the earliest possible start time
        if not runnable_tasks:
            if next_possible_start_time == float('inf'):
                break # No tasks to advance time to
            # arlind: The actual "jump". We fast-forward current_time to the moment the data arrives.
            current_time = next_possible_start_time
            # Re-evaluate who can run at this new time
            runnable_tasks = [
                t for t in ready_tasks 
                if max([completion_times.get(p, 0) for p in G.predecessors(t)], default=0) <= current_time
            ]

        if not runnable_tasks:
            break

        # From the tasks that can start now, pick one by EDF policy (with tie-breaking)
        # arlind: EDF rule -> Sort by the smallest (earliest) deadline. If tied, sort by task ID.
        runnable_tasks.sort(key=lambda tid: (G.nodes[tid]['deadline'], tid))
        task_id = runnable_tasks[0]
        task_data = G.nodes[task_id]

        # Schedule this task
        start_time = current_time
        end_time = start_time + task_data["wcet"]

        # arlind: Hard real-time check. Only save to schedule if it meets the deadline.
        if end_time <= task_data["deadline"]:
            schedule.append({
                "task_id": task_id, "node_id": 0, "start_time": start_time,
                "end_time": end_time, "deadline": task_data["deadline"]
            })
            current_time = end_time
            completion_times[task_id] = end_time
        else:
            missed_deadlines.append(task_id)
        
        tasks_to_schedule.remove(task_id)

    schedule.sort(key=lambda x: x["start_time"])
   
    
    return {
        "schedule": schedule,
        "missed_deadlines": missed_deadlines,
        "name": "EDF Single-node"
    }

def ldf_single_node(application_data):
    """
    Schedule jobs on a single node using the Latest Deadline First (LDF) strategy.
    This function uses a static LDF priority list and schedules the highest-priority
    ready task whenever the processor is free.
    """
    G = build_dependency_graph(application_data)
    schedule = []
    
    # --- LDF Static Ordering Phase ---
    # arlind: LDF works entirely backwards for its planning phase. 
    tasks_to_order = list(G.nodes())
    ordered_task_ids = []
    while tasks_to_order:
        ready_to_order = []
        for task_id in tasks_to_order:
            # arlind: Because we are building the list backwards, we look for "Sink" nodes—tasks 
            # where all their SUCCESSORS have already been ordered.
            if all(succ_id in ordered_task_ids for succ_id in G.successors(task_id)):
                ready_to_order.append(task_id)
        if not ready_to_order:
            break
        # arlind: Among these tail nodes, we pick the one with the absolutely LATEST deadline to execute last.
        ready_to_order.sort(key=lambda tid: (G.nodes[tid]['deadline'], tid), reverse=True)
        task_to_add = ready_to_order[0]
        ordered_task_ids.append(task_to_add)
        tasks_to_order.remove(task_to_add)
    # arlind: Now that we planned it backwards, we reverse the list so we can actually execute it forward from t=0.
    ordered_task_ids.reverse()

    # --- Scheduling Phase (List Scheduling) ---
    completion_times = {}
    current_time = 0
    unscheduled_tasks = ordered_task_ids.copy()
    
    while unscheduled_tasks:
        made_progress = False
        # Find the highest priority task that is ready to run
        for task_id in unscheduled_tasks:
            task_data = G.nodes[task_id]
            predecessors = list(G.predecessors(task_id))

            # arlind: Ensure all data has arrived.
            if not all(p in completion_times for p in predecessors):
                continue

            # Task is ready, calculate start time
            predecessor_end_time = max([completion_times.get(p, 0) for p in predecessors], default=0)
            # arlind: The CPU might be free at t=10, but if data arrives at t=30, start_time must be 30.
            start_time = max(current_time, predecessor_end_time)
            end_time = start_time + task_data['wcet']

            # arlind: HARD REAL-TIME CHECK. If it's going to be late, we refuse to schedule it at all.
            if end_time <= task_data['deadline']:
                schedule.append({
                    "task_id": task_id, "node_id": 0, "start_time": start_time,
                    "end_time": end_time, "deadline": task_data['deadline']
                })
                current_time = end_time
                completion_times[task_id] = end_time
            
            unscheduled_tasks.remove(task_id)
            made_progress = True
            break  # Rescan from the top of the priority list

        if not made_progress:
            break
    
    # arlind: Any task that wasn't scheduled is dumped into the missed_deadlines list.
    all_task_ids = set(G.nodes())
    scheduled_ids = set(completion_times.keys())
    missed_deadlines = sorted(list(all_task_ids - scheduled_ids))

    return {"schedule": schedule, "missed_deadlines": missed_deadlines, "name": "LDF Single-node"}

def ll_multinode_no_delay(application_data, platform_data):
    """
    Schedule jobs on a distributed system with multiple compute nodes using the Least Laxity (LL) strategy.
    This function schedules jobs based on their laxity, with the job having the least laxity being scheduled first.
    """
    G = build_dependency_graph(application_data)
    schedule = []
    scheduled_tasks = set()
    missed_deadlines = []
    
    num_nodes = len(platform_data['nodes'])
    # arlind: We track the free time of EVERY node independently now.
    node_availability = [0] * num_nodes
    
    while len(scheduled_tasks) < len(application_data['tasks']):
        ready_tasks = get_ready_tasks(G, scheduled_tasks)
        
        if not ready_tasks:
            remaining_tasks = set(G.nodes()) - scheduled_tasks
            missed_deadlines.extend(remaining_tasks)
            break
        
        # arlind: Laxity Formula = Deadline - Execution Time (wcet) - Earliest Possible Start Time.
        # Laxity is the "slack" or breathing room a task has. If it hits 0, it must run NOW or it will fail.
        task_laxities = []
        for task_id in ready_tasks:
            task_data = G.nodes[task_id]
            predecessor_end_time = get_predecessor_end_time(G, task_id, schedule)
            # arlind: The earliest it can start is when data arrives AND the earliest available node is free.
            earliest_available_time = max(predecessor_end_time, min(node_availability))
            laxity = task_data['deadline'] - task_data['wcet'] - earliest_available_time
            task_laxities.append((laxity, task_id))
        
        # arlind: Sort to find the task with the LEAST laxity (most urgent).
        task_laxities.sort()
        task_id = task_laxities[0][1]
        task_data = G.nodes[task_id]
        
        predecessor_end_time = get_predecessor_end_time(G, task_id, schedule)
        
        # arlind: Now that we picked the task, we must find the BEST node for it. 
        # We iterate through all nodes and find the one that allows the earliest start time.
        best_node = 0
        best_start_time = max(predecessor_end_time, node_availability[0])
        
        for node_id in range(1, num_nodes):
            candidate_start_time = max(predecessor_end_time, node_availability[node_id])
            if candidate_start_time < best_start_time:
                best_node = node_id
                best_start_time = candidate_start_time
        
        start_time = best_start_time
        end_time = start_time + task_data['wcet']
        
        # arlind: Hard real-time check. If late, throw it away.
        if end_time > task_data['deadline']:
            missed_deadlines.append(task_id)
            scheduled_tasks.add(task_id) 
            continue
        
        schedule.append({
            "task_id": task_id,
            "node_id": best_node,
            "start_time": start_time,
            "end_time": end_time,
            "deadline": task_data['deadline']
        })
        
        scheduled_tasks.add(task_id)
        # arlind: Update only the specific node we used so it's locked until 'end_time'.
        node_availability[best_node] = end_time

    return {"schedule": schedule, "missed_deadlines": sorted(list(set(missed_deadlines))), "name": "LL(without delay)"}


def ldf_multinode_no_delay(application_data, platform_data):
    """
    Schedules jobs on multiple nodes using the static Latest Deadline First (LDF)
    list scheduling algorithm for a Directed Acyclic Graph (DAG) of tasks.
    """
    G = build_dependency_graph(application_data)
    schedule = []
    completion_times = {}  # Tracks finish time for each scheduled task
    missed_deadlines = []

    # --- Setup: Initialize compute nodes and their availability (SNIPPET 1) ---
    try:
        # Extract compute nodes from platform data
        # arlind: This explicitly filters out any nodes that aren't labeled "compute" (e.g. ignoring network switches).
        compute_nodes = [node["id"] for node in platform_data["nodes"] if node["type"] == "compute"]
        if not compute_nodes:
            return {"schedule": [], "missed_deadlines": sorted(list(G.nodes())), "name": "LDF Multinode(without delay)"}
    except (KeyError, TypeError):
        return {"schedule": [], "missed_deadlines": sorted(list(G.nodes())), "name": "LDF Multinode(without delay)"}

    # Keep track of when each compute node will be available next
    node_availability = {node_id: 0 for node_id in compute_nodes}

    # --- Phase 1: LDF Static Priority List Generation (SNIPPET 2 Logic) ---
    ordered_tasks = []  # Final ordered list of tasks
    copyOfTasks = [G.nodes[task_id] for task_id in G.nodes()]  # Copy of all tasks with their data
    
    # Start with tasks that have no successors (sink nodes)
    no_successor = []
    for task_id in G.nodes():
        if len(list(G.successors(task_id))) == 0:  # No successors = sink node
            task_data = G.nodes[task_id].copy()
            task_data['id'] = task_id  # Ensure task has id field
            no_successor.append(task_data)

    while copyOfTasks:
        # No tasks without successor left
        if not no_successor:
            break
        
        # Sort after latest deadline (LDF)
        no_successor.sort(key=lambda task: (task["deadline"]), reverse=True)
        selected_task = no_successor[0]  # First entry has highest deadline after sorting
        
        # Add task to order and remove it from other lists
        ordered_tasks.append(selected_task)
        no_successor.remove(selected_task)
        copyOfTasks = [task for task in copyOfTasks if task.get('id', task.get('task_id')) != selected_task['id']]
        
        # Find eligible predecessors (all of whose successors are already scheduled)
        # arlind: As we move backwards, we "unlock" the predecessors once all their successors are accounted for.
        for pred_id in G.predecessors(selected_task["id"]):
            # Check if all successors are already in ordered_tasks
            all_successors_scheduled = True
            for succ in G.successors(pred_id):
                if not any(task["id"] == succ for task in ordered_tasks):
                    all_successors_scheduled = False
                    break
            
            if all_successors_scheduled:
                pred_data = G.nodes[pred_id].copy()
                pred_data['id'] = pred_id
                # Only add if not already in no_successor list
                if not any(task["id"] == pred_id for task in no_successor):
                    no_successor.append(pred_data)

    # Reverse the list to get the correct LDF order (from leaves to root)
    ordered_tasks.reverse()

    # Create priority list with just task IDs for easier processing
    priority_list = [task['id'] for task in ordered_tasks]

    # --- Phase 2: List Scheduling ---
    # arlind: Now we go forwards through time, using the static priority list we just built.
    for task_id in priority_list:
        if task_id in missed_deadlines:
            continue

        task_data = G.nodes[task_id]
        
        # Determine the earliest time the task can start based on predecessor completion
        predecessor_end_time = 0
        all_predecessors_scheduled = True
        for pred_id in G.predecessors(task_id):
            if pred_id in completion_times:
                predecessor_end_time = max(predecessor_end_time, completion_times[pred_id])
            else:
                # arlind: If a predecessor failed (missed deadline), this task is starved of data and automatically fails too.
                all_predecessors_scheduled = False
                break
        
        if not all_predecessors_scheduled:
            missed_deadlines.append(task_id)
            continue

        # Find the best node for this task (SNIPPET 3 Logic)
        # arlind: A Greedy approach -> simply assign the task to whichever node frees up the earliest.
        chosen_node = min(compute_nodes, key=lambda node: node_availability.get(node, 0))
        
        # Calculate start and finish times
        start_time = max(node_availability[chosen_node], predecessor_end_time)
        finish_time = start_time + task_data['wcet']

        # Schedule the task if it does not miss its deadline
        if finish_time <= task_data['deadline']:
            schedule.append({
                "task_id": task_id,
                "node_id": chosen_node,
                "start_time": start_time,
                "end_time": finish_time,
                "deadline": task_data['deadline']
            })
            completion_times[task_id] = finish_time
            node_availability[chosen_node] = finish_time
        else:
            missed_deadlines.append(task_id)
    
    schedule.sort(key=lambda x: x['start_time'])
    
    return {
        "schedule": schedule,
        "missed_deadlines": sorted(list(set(missed_deadlines))),
        "name": "LDF Multinode(without delay)"
    }


def edf_multinode_no_delay(application_data, platform_data):
    """
    Schedule jobs on a distributed system with multiple compute nodes using the Earliest Deadline First (EDF) strategy.
    """
    G = build_dependency_graph(application_data)
    schedule = []
    scheduled_tasks = set()
    missed_deadlines = []
    
    # FIX: Filter for compute nodes only, just like LDF
    try:
        compute_nodes = [node["id"] for node in platform_data["nodes"] if node["type"] == "compute"]
        if not compute_nodes:
            return {"schedule": [], "missed_deadlines": sorted(list(G.nodes())), "name": "EDF Multinode(without delay)"}
    except (KeyError, TypeError):
        return {"schedule": [], "missed_deadlines": sorted(list(G.nodes())), "name": "EDF Multinode(without delay)"}

    # FIX: Use a dictionary for node availability so it maps safely to exact IDs
    node_availability = {node_id: 0 for node_id in compute_nodes}
    
    while len(scheduled_tasks) < len(application_data['tasks']):
        ready_tasks = get_ready_tasks(G, scheduled_tasks)
        
        if not ready_tasks:
            remaining_tasks = set(G.nodes()) - scheduled_tasks
            missed_deadlines.extend(remaining_tasks)
            break
            
        ready_tasks.sort(key=lambda x: (G.nodes[x]['deadline'], x))
        
        task_id = ready_tasks[0]
        task_data = G.nodes[task_id]
        
        predecessor_end_time = get_predecessor_end_time(G, task_id, schedule)
        
        # FIX: Find the best node safely iterating over the compute_nodes dictionary
        best_node = min(compute_nodes, key=lambda nid: max(predecessor_end_time, node_availability[nid]))
        best_start_time = max(predecessor_end_time, node_availability[best_node])
        
        start_time = best_start_time
        end_time = start_time + task_data['wcet']
        
        if end_time > task_data['deadline']:
            missed_deadlines.append(task_id)
            scheduled_tasks.add(task_id)
            continue
                  
        schedule.append({
            "task_id": task_id,
            "node_id": best_node,
            "start_time": start_time,
            "end_time": end_time,
            "deadline": task_data['deadline']
        })
        
        scheduled_tasks.add(task_id)
        node_availability[best_node] = end_time

    return {"schedule": schedule, "missed_deadlines": sorted(list(set(missed_deadlines))), "name": "EDF Multinode(without delay)"}
