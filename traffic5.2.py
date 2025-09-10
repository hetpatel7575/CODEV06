import tkinter as tk
from tkinter import ttk
import random
import time

# -----------------------------
# Global Simulation State
# -----------------------------
is_paused = False
cycle_number = 0
active_lane_index = -1  # Start at -1 so the first run initializes to lane 0
time_left = 0
current_traffic_counts = {}
current_durations = {}
lanes = ["North", "South", "East", "West"]
time_of_day_var = None # Will be initialized as a Tkinter StringVar
simulation_speed = 100  # ms between updates
sound_effects = True
performance_stats = {
    "total_cars_passed": 0,
    "avg_wait_time": 0,
    "max_wait_time": 0,
    "start_time": time.time()
}

# Stop line positions for each lane
stop_lines = {
    "North": 240,
    "South": 360,
    "East": 360,
    "West": 240
}

# Car data structure to track individual car information
car_data = {
    "North": [],
    "South": [],
    "East": [],
    "West": []
}

# -----------------------------
# Sound Effects
# -----------------------------
def play_sound(sound_type):
    """Plays sound effects if enabled"""
    if not sound_effects:
        return
    
    # In a real implementation, you would use playsound or pygame for audio
    # This is a placeholder that just prints the sound event
    sound_messages = {
        "light_change": "🔊 Traffic light changed",
        "car_passed": "🔊 Car passed intersection",
        "horn": "🔊 Car horn sound",
        "sim_start": "🔊 Simulation started",
        "sim_pause": "🔊 Simulation paused"
    }
    
    if sound_type in sound_messages:
        print(sound_messages[sound_type])

# -----------------------------
# AI Logic to Get Signal Durations
# -----------------------------
def get_signal_durations(traffic_counts, time_of_day):
    """Calculates green light durations based on traffic and time."""
    total_traffic = sum(traffic_counts.values())
    durations = {}
    min_duration = 10   # Minimum green time to prevent instant switching
    max_duration = 40  # Maximum green time
    total_cycle_time = 90 # Total time for one full cycle

    if total_traffic == 0:
        return {lane: min_duration for lane in traffic_counts}

    # Proportional allocation
    for lane, count in traffic_counts.items():
        # Base duration is proportional to traffic, clamped to min/max
        duration = int((count / total_traffic) * total_cycle_time)
        durations[lane] = max(min_duration, min(duration, max_duration))

    # Time-of-day bias (simulated AI "learning")
    if time_of_day == "Morning":
        # Boost North-South for morning commute
        durations["North"] = min(durations["North"] + 15, max_duration)
        durations["South"] = min(durations["South"] + 15, max_duration)
    elif time_of_day == "Evening":
        # Boost East-West for evening commute
        durations["East"] = min(durations["East"] + 15, max_duration)
        durations["West"] = min(durations["West"] + 15, max_duration)

    return durations

# -----------------------------
# GUI Setup
# -----------------------------
root = tk.Tk()
root.title("Enhanced AI Traffic Simulation")

# Main canvas for the simulation
canvas = tk.Canvas(root, width=600, height=600, bg="#DDDDDD")
canvas.grid(row=0, column=0, rowspan=15, padx=10, pady=10)

# Draw roads
canvas.create_rectangle(250, 0, 350, 600, fill="gray20", outline="") # Vertical road
canvas.create_rectangle(0, 250, 600, 350, fill="gray20", outline="") # Horizontal road
# Center intersection
canvas.create_rectangle(250, 250, 350, 350, fill="gray20", outline="")
# Lane lines
for i in range(0, 601, 20): # Horizontal lines
    canvas.create_line(0, 299, 240, 299, fill="yellow", dash=(4, 8))
    canvas.create_line(360, 299, 600, 299, fill="yellow", dash=(4, 8))
for i in range(0, 601, 20): # Vertical lines
    canvas.create_line(299, 0, 299, 240, fill="yellow", dash=(4, 8))
    canvas.create_line(299, 360, 299, 600, fill="yellow", dash=(4, 8))

# Draw stop lines
canvas.create_line(240, 250, 240, 350, fill="white", width=3)  # West stop line
canvas.create_line(360, 250, 360, 350, fill="white", width=3)  # East stop line
canvas.create_line(250, 240, 350, 240, fill="white", width=3)  # North stop line
canvas.create_line(250, 360, 350, 360, fill="white", width=3)  # South stop line

# Draw traffic lights
lights = {
    "North": canvas.create_oval(260, 210, 290, 240, fill="red", outline="black", width=2),
    "South": canvas.create_oval(310, 360, 340, 390, fill="red", outline="black", width=2),
    "East":  canvas.create_oval(360, 260, 390, 290, fill="red", outline="black", width=2),
    "West":  canvas.create_oval(210, 310, 240, 340, fill="red", outline="black", width=2),
}

# Car objects - will be generated dynamically
cars = {
    "North": [],
    "South": [],
    "East": [],
    "West": []
}
car_speed = 5
car_length = 30
car_spacing = 10

# -----------------------------
# Side Panel for Controls and Info
# -----------------------------
control_frame = tk.Frame(root, padx=10, pady=10)
control_frame.grid(row=0, column=1, rowspan=15, sticky="n")

# --- Title and Control Buttons ---
tk.Label(control_frame, text="Simulation Control", font=("Arial", 16, "bold")).pack(pady=10, anchor="w")

button_frame = tk.Frame(control_frame)
button_frame.pack(pady=5, fill="x")

pause_button = tk.Button(button_frame, text="Pause", width=12)
pause_button.pack(side=tk.LEFT, padx=5)

reset_button = tk.Button(button_frame, text="Reset", width=12)
reset_button.pack(side=tk.LEFT, padx=5)

# --- Time of Day Selector ---
tk.Label(control_frame, text="Time of Day:", font=("Arial", 12, "bold")).pack(pady=(10,0), anchor="w")
time_of_day_var = tk.StringVar(value="Normal")
times = ["Normal", "Morning", "Evening"]
for time in times:
    ttk.Radiobutton(control_frame, text=time, variable=time_of_day_var, value=time).pack(anchor="w")

# --- Sound Effects Toggle ---
sound_var = tk.BooleanVar(value=True)
sound_check = ttk.Checkbutton(control_frame, text="Enable Sound Effects", variable=sound_var)
sound_check.pack(pady=5, anchor="w")

# --- Simulation Speed Control ---
tk.Label(control_frame, text="Simulation Speed:", font=("Arial", 10, "bold")).pack(pady=(10,0), anchor="w")
speed_scale = tk.Scale(control_frame, from_=50, to=500, orient=tk.HORIZONTAL, 
                      showvalue=False, length=150)
speed_scale.set(100)
speed_scale.pack(anchor="w", pady=5)

speed_value_label = tk.Label(control_frame, text="Normal")
speed_value_label.pack(anchor="w")

# --- Dynamic Info Labels ---
info_frame = tk.Frame(control_frame, pady=10)
info_frame.pack(pady=10, fill="x")

tk.Label(info_frame, text="Cycle Number:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w")
cycle_label = tk.Label(info_frame, text="0", font=("Arial", 10))
cycle_label.grid(row=0, column=1, sticky="w")

tk.Label(info_frame, text="Active Lane:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w")
active_lane_label = tk.Label(info_frame, text="None", font=("Arial", 10), fg="green")
active_lane_label.grid(row=1, column=1, sticky="w")

tk.Label(info_frame, text="Time Left:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w")
time_left_label = tk.Label(info_frame, text="0s", font=("Arial", 10))
time_left_label.grid(row=2, column=1, sticky="w")

# --- Performance Statistics ---
tk.Label(control_frame, text="Performance Stats", font=("Arial", 12, "bold")).pack(pady=(10,0), anchor="w")
stats_frame = tk.Frame(control_frame)
stats_frame.pack(pady=5, fill="x")

tk.Label(stats_frame, text="Cars Passed:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w")
cars_passed_label = tk.Label(stats_frame, text="0", font=("Arial", 9))
cars_passed_label.grid(row=0, column=1, sticky="w")

tk.Label(stats_frame, text="Avg Wait Time:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w")
avg_wait_label = tk.Label(stats_frame, text="0s", font=("Arial", 9))
avg_wait_label.grid(row=1, column=1, sticky="w")

tk.Label(stats_frame, text="Max Wait Time:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w")
max_wait_label = tk.Label(stats_frame, text="0s", font=("Arial", 9))
max_wait_label.grid(row=2, column=1, sticky="w")

# --- Traffic and Duration Display ---
traffic_frame = tk.Frame(control_frame)
traffic_frame.pack(pady=10)
tk.Label(traffic_frame, text="Lane", font=("Arial", 10, "bold")).grid(row=0, column=0)
tk.Label(traffic_frame, text="Cars", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=10)
tk.Label(traffic_frame, text="Green (s)", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=10)
tk.Label(traffic_frame, text="Queue", font=("Arial", 10, "bold")).grid(row=0, column=3, padx=10)

lane_labels = {}
for i, lane in enumerate(lanes):
    tk.Label(traffic_frame, text=f"{lane}:").grid(row=i+1, column=0, sticky="w")
    car_count_label = tk.Label(traffic_frame, text="0")
    car_count_label.grid(row=i+1, column=1)
    duration_label = tk.Label(traffic_frame, text="0s")
    duration_label.grid(row=i+1, column=2)
    queue_label = tk.Label(traffic_frame, text="0")
    queue_label.grid(row=i+1, column=3)
    lane_labels[lane] = (car_count_label, duration_label, queue_label)

# -----------------------------
# Simulation Logic
# -----------------------------

def toggle_pause():
    """Toggles the simulation's paused state."""
    global is_paused
    is_paused = not is_paused
    pause_button.config(text="Resume" if is_paused else "Pause")
    play_sound("sim_pause" if is_paused else "sim_start")

def reset_simulation():
    """Resets the simulation to initial state."""
    global is_paused, cycle_number, active_lane_index, time_left
    global current_traffic_counts, current_durations, performance_stats, car_data
    
    # Reset simulation state
    is_paused = False
    cycle_number = 0
    active_lane_index = -1
    time_left = 0
    current_traffic_counts = {}
    current_durations = {}
    
    # Reset performance stats
    performance_stats = {
        "total_cars_passed": 0,
        "avg_wait_time": 0,
        "max_wait_time": 0,
        "start_time": time.time()
    }
    
    # Clear all cars from the canvas and data
    for lane in lanes:
        for car_id in cars[lane]:
            canvas.delete(car_id)
        cars[lane] = []
        car_data[lane] = []
    
    # Reset UI elements
    pause_button.config(text="Pause")
    update_performance_stats()
    
    # Start new cycle
    start_new_cycle()

def generate_car(lane):
    """Generates a new car in the specified lane with a random color."""
    colors = ["dodger blue", "orange red", "purple", "lawn green", "cyan", "yellow", "pink"]
    color = random.choice(colors)
    
    if lane == "North":
        car_id = canvas.create_rectangle(265, -car_length, 285, 0, fill=color)
        cars[lane].append(car_id)
        car_data[lane].append({
            "id": car_id,
            "wait_time": 0,
            "passed": False,
            "position": -car_length
        })
    elif lane == "South":
        car_id = canvas.create_rectangle(315, 600, 335, 600+car_length, fill=color)
        cars[lane].append(car_id)
        car_data[lane].append({
            "id": car_id,
            "wait_time": 0,
            "passed": False,
            "position": 600
        })
    elif lane == "East":
        car_id = canvas.create_rectangle(600, 315, 600+car_length, 335, fill=color)
        cars[lane].append(car_id)
        car_data[lane].append({
            "id": car_id,
            "wait_time": 0,
            "passed": False,
            "position": 600
        })
    elif lane == "West":
        car_id = canvas.create_rectangle(-car_length, 265, 0, 285, fill=color)
        cars[lane].append(car_id)
        car_data[lane].append({
            "id": car_id,
            "wait_time": 0,
            "passed": False,
            "position": -car_length
        })

def remove_passed_cars():
    """Removes cars that have passed the intersection from the simulation."""
    for lane in lanes:
        i = 0
        while i < len(car_data[lane]):
            car = car_data[lane][i]
            car_id = car["id"]
            
            # Check if car has passed the intersection and is off screen
            coords = canvas.coords(car_id)
            is_off_screen = False
            
            if lane == "North" and coords[1] > 600:
                is_off_screen = True
            elif lane == "South" and coords[3] < 0:
                is_off_screen = True
            elif lane == "East" and coords[2] < 0:
                is_off_screen = True
            elif lane == "West" and coords[0] > 600:
                is_off_screen = True
                
            if is_off_screen:
                canvas.delete(car_id)
                cars[lane].pop(i)
                car_data[lane].pop(i)
                
                # Update performance stats
                if car["passed"]:
                    performance_stats["total_cars_passed"] += 1
                    performance_stats["avg_wait_time"] = (
                        (performance_stats["avg_wait_time"] * (performance_stats["total_cars_passed"] - 1) + 
                         car["wait_time"]) / performance_stats["total_cars_passed"]
                    )
                    performance_stats["max_wait_time"] = max(
                        performance_stats["max_wait_time"], car["wait_time"]
                    )
            else:
                i += 1

def move_cars():
    """Moves cars based on traffic light status and position, ensuring no collisions."""
    for lane, car_list in cars.items():
        is_green = canvas.itemcget(lights[lane], "fill") == "green"
        stop_line = stop_lines[lane]
        
        for i, car_id in enumerate(car_list):
            car_info = car_data[lane][i]
            coords = canvas.coords(car_id)
            move = False
            
            # Check if car can move (no car too close in front)
            can_move = True
            if i > 0:  # Not the first car in the lane
                front_car_coords = canvas.coords(cars[lane][i-1])
                if lane == "North" and coords[1] - front_car_coords[3] < car_spacing:
                    can_move = False
                elif lane == "South" and front_car_coords[1] - coords[3] < car_spacing:
                    can_move = False
                elif lane == "East" and front_car_coords[0] - coords[2] < car_spacing:
                    can_move = False
                elif lane == "West" and coords[0] - front_car_coords[2] < car_spacing:
                    can_move = False
            
            # Determine if car should move based on light and position
            if lane == "North":
                # Car is before stop line - can approach even during red light
                if coords[3] < stop_line:
                    # If green light or there's space to approach the stop line
                    if (is_green or coords[3] + car_speed < stop_line) and can_move:
                        move = True
                        if not is_green:
                            car_info["wait_time"] += 0.1  # Increment wait time only if at red light
                else:  # Car is past stop line - can continue
                    if can_move:
                        move = True
                        if not car_info["passed"]:
                            car_info["passed"] = True
                            play_sound("car_passed")
                
                if move: 
                    canvas.move(car_id, 0, car_speed)
                    car_info["position"] += car_speed
                    
            elif lane == "South":
                if coords[1] > stop_line:
                    if (is_green or coords[1] - car_speed > stop_line) and can_move:
                        move = True
                        if not is_green:
                            car_info["wait_time"] += 0.1
                else:
                    if can_move:
                        move = True
                        if not car_info["passed"]:
                            car_info["passed"] = True
                            play_sound("car_passed")
                
                if move: 
                    canvas.move(car_id, 0, -car_speed)
                    car_info["position"] -= car_speed
                    
            elif lane == "East":
                if coords[0] > stop_line:
                    if (is_green or coords[0] - car_speed > stop_line) and can_move:
                        move = True
                        if not is_green:
                            car_info["wait_time"] += 0.1
                else:
                    if can_move:
                        move = True
                        if not car_info["passed"]:
                            car_info["passed"] = True
                            play_sound("car_passed")
                
                if move: 
                    canvas.move(car_id, -car_speed, 0)
                    car_info["position"] -= car_speed
                    
            elif lane == "West":
                if coords[2] < stop_line:
                    if (is_green or coords[2] + car_speed < stop_line) and can_move:
                        move = True
                        if not is_green:
                            car_info["wait_time"] += 0.1
                else:
                    if can_move:
                        move = True
                        if not car_info["passed"]:
                            car_info["passed"] = True
                            play_sound("car_passed")
                
                if move: 
                    canvas.move(car_id, car_speed, 0)
                    car_info["position"] += car_speed
            
            # If car is waiting at red light and not moving, increment wait time
            if not move and not car_info["passed"] and not is_green and (
                (lane == "North" and coords[3] >= stop_line - car_speed and coords[3] < stop_line) or
                (lane == "South" and coords[1] <= stop_line + car_speed and coords[1] > stop_line) or
                (lane == "East" and coords[0] <= stop_line + car_speed and coords[0] > stop_line) or
                (lane == "West" and coords[2] >= stop_line - car_speed and coords[2] < stop_line)
            ):
                car_info["wait_time"] += 0.1

def update_performance_stats():
    """Updates the performance statistics display."""
    cars_passed_label.config(text=str(performance_stats["total_cars_passed"]))
    avg_wait_label.config(text=f"{performance_stats['avg_wait_time']:.1f}s")
    max_wait_label.config(text=f"{performance_stats['max_wait_time']:.1f}s")

def start_new_cycle():
    """Initiates the next traffic light cycle."""
    global cycle_number, active_lane_index, time_left, current_traffic_counts, current_durations

    # Deactivate the previous light
    if active_lane_index != -1:
        prev_lane = lanes[active_lane_index]
        canvas.itemconfig(lights[prev_lane], fill="red")

    # Move to the next lane in sequence
    active_lane_index = (active_lane_index + 1) % len(lanes)
    active_lane = lanes[active_lane_index]

    # If we completed a full loop, increment cycle number and get new AI data
    if active_lane_index == 0:
        cycle_number += 1
        # Generate new random traffic counts for this cycle
        current_traffic_counts = {lane: random.randint(5, 50) for lane in lanes}
        # Get AI-calculated durations
        current_durations = get_signal_durations(current_traffic_counts, time_of_day_var.get())

    # Set the time for the new active lane
    time_left = current_durations[active_lane]

    # Activate the new light
    canvas.itemconfig(lights[active_lane], fill="green")
    play_sound("light_change")

    # Update GUI Labels
    cycle_label.config(text=str(cycle_number))
    for lane in lanes:
        lane_labels[lane][0].config(text=str(current_traffic_counts.get(lane, 0)))
        lane_labels[lane][1].config(text=f"{current_durations.get(lane, 0)}s")
        # Update queue length
        queue_count = sum(1 for car in car_data[lane] if not car["passed"])
        lane_labels[lane][2].config(text=str(queue_count))

def update_simulation():
    """The main loop that runs every 100ms to update the simulation."""
    global time_left, simulation_speed, sound_effects

    if not is_paused:
        # Update simulation speed based on slider
        simulation_speed = speed_scale.get()
        speed_labels = {
            50: "Very Fast",
            100: "Fast",
            200: "Normal",
            300: "Slow",
            500: "Very Slow"
        }
        closest_speed = min(speed_labels.keys(), key=lambda x: abs(x - simulation_speed))
        speed_value_label.config(text=speed_labels[closest_speed])
        
        # Update sound effects setting
        sound_effects = sound_var.get()
        
        # Generate cars based on traffic counts - more cars for lanes with higher traffic
        for lane in lanes:
            traffic_count = current_traffic_counts.get(lane, 5)
            # Calculate probability based on traffic count (higher count = higher probability)
            probability = min(0.3, 0.05 + (traffic_count / 200))
            if random.random() < probability:
                generate_car(lane)
        
        move_cars()
        remove_passed_cars()
        update_performance_stats()
        
        if time_left > 0:
            time_left -= 0.1
        else:
            start_new_cycle()

        # Update dynamic labels
        if active_lane_index >= 0:
            active_lane = lanes[active_lane_index]
            active_lane_label.config(text=active_lane, fg="green" if canvas.itemcget(lights[active_lane], "fill") == "green" else "red")
            time_left_label.config(text=f"{time_left:.1f}s")

    # Schedule the next update
    root.after(int(simulation_speed), update_simulation)

# -----------------------------
# Start the Simulation
# -----------------------------
pause_button.config(command=toggle_pause)
reset_button.config(command=reset_simulation)
start_new_cycle()  # Initialize the first cycle
update_simulation() # Start the main loop
root.mainloop()
