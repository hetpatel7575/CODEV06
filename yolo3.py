import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading
import cv2
import numpy as np
import os
from PIL import Image, ImageTk
# Note: You'll need to install ultralytics for YOLO: pip install ultralytics
from ultralytics import YOLO

# Global variables
is_paused = False
active_direction = None
time_left = 0
current_traffic_counts = {}
current_durations = {}
total_cars_passed = 0
cars_on_screen = 0
yolo_inputs_received = {direction: False for direction in ["North", "South", "East", "West"]}
yolo_counts = {direction: 0 for direction in ["North", "South", "East", "West"]}
simulation_started = False

directions = ["North", "South", "East", "West"]
active_direction_sequence = ["North", "South", "East", "West"]
active_direction_index = -1

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 800
ROAD_WIDTH = 200
LANE_WIDTH = 50
CENTER = CANVAS_WIDTH / 2
INTERSECTION_START = CENTER - (ROAD_WIDTH / 2)
INTERSECTION_END = CENTER + (ROAD_WIDTH / 2)
STOP_LINE_MARGIN = 15
CAR_LENGTH = 30
CAR_WIDTH = 20
SAFE_DISTANCE = 15
MAX_CARS_PER_LANE = 20
BASE_CAR_SPEED = 5.0

# Track last spawn time for each direction to add delays
last_spawn_time = {direction: 0 for direction in directions}

# YOLO model initialization - Update this path to your actual YOLO model
# For example: "yolov8n.pt", "yolov8s.pt", or your custom trained model
YOLO_MODEL_PATH = r"C:\Python\traffic_image"  # Replace with your actual model path

# Directory for traffic images
TRAFFIC_IMAGE_DIR = r"C:\Python\traffic_image"

# Initialize YOLO model
try:
    yolo_model = YOLO(YOLO_MODEL_PATH)
    print(f"YOLO model loaded successfully from {YOLO_MODEL_PATH}")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    yolo_model = None

class Car:
    def __init__(self, canvas, lane_name, color):
        self.canvas = canvas
        self.lane_name = lane_name
        self.direction = lane_name.split("_")[0]
        self.orientation = "vertical" if self.direction in ["North", "South"] else "horizontal"
        self.is_active = False
        self.waiting_at_light = False
        self.has_passed_intersection = False
        self.is_in_intersection = False
        self.has_entered_intersection = False  # NEW: Track if car has entered intersection

        w, l = (CAR_WIDTH, CAR_LENGTH) if self.orientation == "vertical" else (CAR_LENGTH, CAR_WIDTH)
        self.body = self.canvas.create_rectangle(0, 0, w, l, fill=color, outline="black", state=tk.HIDDEN)
        self.cabin = self.canvas.create_rectangle(2, l * 0.2, w - 2, l * 0.7, fill="light gray", outline="black", state=tk.HIDDEN)
        self.graphic = (self.body, self.cabin)

    def set_state(self, state):
        for item in self.graphic:
            self.canvas.itemconfig(item, state=state)

    def activate(self, x=None, y=None):
        global cars_on_screen
        self.is_active = True
        self.waiting_at_light = False
        self.has_passed_intersection = False
        self.is_in_intersection = False
        self.has_entered_intersection = False  # Reset
        cars_on_screen += 1
        
        if x is None or y is None:
            # Default spawn position
            if self.direction == "North":
                lane_offset = 0 if "_L" in self.lane_name else -LANE_WIDTH
                x, y = CENTER - LANE_WIDTH + lane_offset, -CAR_LENGTH
            elif self.direction == "South":
                lane_offset = 0 if "_L" in self.lane_name else LANE_WIDTH
                x, y = CENTER + lane_offset, CANVAS_HEIGHT
            elif self.direction == "West":
                lane_offset = 0 if "_L" in self.lane_name else -LANE_WIDTH
                x, y = -CAR_LENGTH, CENTER - LANE_WIDTH + lane_offset
            elif self.direction == "East":
                lane_offset = 0 if "_L" in self.lane_name else LANE_WIDTH
                x, y = CANVAS_WIDTH, CENTER + lane_offset

        current_coords = self.get_coords()
        self.move(x - current_coords[0], y - current_coords[1])
        self.set_state(tk.NORMAL)

    def deactivate(self):
        global cars_on_screen, total_cars_passed
        if self.is_active:
            self.is_active = False
            self.set_state(tk.HIDDEN)
            cars_on_screen -= 1
            total_cars_passed += 1

    def move(self, dx, dy):
        for item in self.graphic:
            self.canvas.move(item, dx, dy)

    def get_coords(self):
        return self.canvas.coords(self.body)

    def get_front_pos(self):
        coords = self.get_coords()
        if self.direction == "North": return coords[3]
        if self.direction == "South": return coords[1]
        if self.direction == "West": return coords[2]
        if self.direction == "East": return coords[0]
        
    def get_rear_pos(self):
        coords = self.get_coords()
        if self.direction == "North": return coords[1]
        if self.direction == "South": return coords[3]
        if self.direction == "West": return coords[0]
        if self.direction == "East": return coords[2]

    def is_offscreen(self):
        coords = self.get_coords()
        return coords[0] > CANVAS_WIDTH + 10 or coords[1] > CANVAS_HEIGHT + 10 or \
               coords[2] < -10 or coords[3] < -10
               
    def is_at_stop_line(self):
        front_pos = self.get_front_pos()
        if self.direction == "North":
            return front_pos >= INTERSECTION_START - STOP_LINE_MARGIN
        elif self.direction == "South":
            return front_pos <= INTERSECTION_END + STOP_LINE_MARGIN
        elif self.direction == "West":
            return front_pos >= INTERSECTION_START - STOP_LINE_MARGIN
        elif self.direction == "East":
            return front_pos <= INTERSECTION_END + STOP_LINE_MARGIN
        return False
        
    def is_in_intersection_area(self):
        coords = self.get_coords()
        x1, y1, x2, y2 = coords
        
        if self.direction == "North":
            return y1 < INTERSECTION_END and y2 > INTERSECTION_START
        elif self.direction == "South":
            return y1 < INTERSECTION_END and y2 > INTERSECTION_START
        elif self.direction == "West":
            return x1 < INTERSECTION_END and x2 > INTERSECTION_START
        elif self.direction == "East":
            return x1 < INTERSECTION_END and x2 > INTERSECTION_START
        return False
        
    def is_past_intersection(self):
        rear_pos = self.get_rear_pos()
        if self.direction == "North":
            return rear_pos > INTERSECTION_END
        elif self.direction == "South":
            return rear_pos < INTERSECTION_START
        elif self.direction == "West":
            return rear_pos > INTERSECTION_END
        elif self.direction == "East":
            return rear_pos < INTERSECTION_START
        return False
        
    def distance_to_intersection(self):
        front_pos = self.get_front_pos()
        if self.direction == "North":
            return max(0, INTERSECTION_START - STOP_LINE_MARGIN - front_pos)
        elif self.direction == "South":
            return max(0, front_pos - (INTERSECTION_END + STOP_LINE_MARGIN))
        elif self.direction == "West":
            return max(0, INTERSECTION_START - STOP_LINE_MARGIN - front_pos)
        elif self.direction == "East":
            return max(0, front_pos - (INTERSECTION_END + STOP_LINE_MARGIN))
        return 0

def get_signal_durations(traffic, time_of_day):
    total_traffic = sum(traffic.values())
    durations = {}
    min_d, max_d, total_cycle = 15, 60, 150
    if total_traffic == 0: return {d: min_d for d in directions}

    for d, count in traffic.items():
        durations[d] = max(min_d, min(max_d, int((count / total_traffic) * total_cycle)))

    if time_of_day == "Morning":
        for d in ["North", "South"]: durations[d] = min(max_d, durations[d] + 25)
    elif time_of_day == "Evening":
        for d in ["East", "West"]: durations[d] = min(max_d, durations[d] + 25)
    return durations

def process_image_with_yolo(direction):
    """Process an image for a specific direction using YOLO and return car count"""
    # Check if YOLO model is loaded
    if yolo_model is None:
        messagebox.showerror("Error", "YOLO model failed to load. Using random counts instead.")
        return random.randint(5, 20)
    
    # Check if directory exists
    if not os.path.exists(TRAFFIC_IMAGE_DIR):
        messagebox.showerror("Error", f"Directory {TRAFFIC_IMAGE_DIR} does not exist!")
        return random.randint(5, 20)
    
    # Look for image files with direction in the name
    image_files = []
    for file in os.listdir(TRAFFIC_IMAGE_DIR):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')) and direction.lower() in file.lower():
            image_files.append(os.path.join(TRAFFIC_IMAGE_DIR, file))
    
    if not image_files:
        messagebox.showerror("Error", f"No image found for {direction} direction in {TRAFFIC_IMAGE_DIR}")
        return random.randint(5, 20)
    
    # Use the first matching image
    file_path = image_files[0]
    
    # Load and process image with YOLO
    try:
        # Read the image
        image = cv2.imread(file_path)
        if image is None:
            messagebox.showerror("Error", f"Could not load image: {file_path}")
            return random.randint(5, 20)
        
        # Run YOLO inference
        results = yolo_model(image)
        
        # Count vehicles (YOLO class 2, 3, 5, 7 are different types of vehicles)
        vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        vehicle_count = 0
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                if class_id in vehicle_classes:
                    vehicle_count += 1
        
        print(f"YOLO detected {vehicle_count} vehicles in {direction} direction")
        return vehicle_count
        
    except Exception as e:
        messagebox.showerror("Error", f"YOLO processing failed: {str(e)}")
        return random.randint(5, 20)

def capture_yolo_input(direction):
    """Capture and process YOLO input for a specific direction"""
    count = process_image_with_yolo(direction)
    yolo_counts[direction] = count
    yolo_inputs_received[direction] = True
    
    # Update the UI
    lane_labels[direction][0].config(text=str(count))
    
    # Check if all inputs are received
    check_all_inputs_received()

def check_all_inputs_received():
    """Check if all lane inputs have been received from YOLO"""
    global simulation_started, current_traffic_counts
    
    if all(yolo_inputs_received.values()) and not simulation_started:
        simulation_started = True
        current_traffic_counts = yolo_counts.copy()
        
        # Start the simulation
        start_new_cycle()
        messagebox.showinfo("Info", "All lane inputs received. Simulation starting!")

def start_yolo_capture():
    """Start the process of capturing YOLO inputs for all lanes"""
    # Reset the received flags
    for direction in directions:
        yolo_inputs_received[direction] = False
        yolo_counts[direction] = 0
        lane_labels[direction][0].config(text="0")
    
    for direction in directions:
        # Use threading to avoid blocking the UI
        thread = threading.Thread(target=capture_yolo_input, args=(direction,))
        thread.daemon = True
        thread.start()

# Create the main window
root = tk.Tk()
root.title("YOLO Integrated Traffic Simulation")
canvas = tk.Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#4F4F4F")
canvas.grid(row=0, column=0, rowspan=20, padx=10, pady=10)

# Draw the intersection
canvas.create_rectangle(INTERSECTION_START, 0, INTERSECTION_END, CANVAS_HEIGHT, fill="gray20", outline="")
canvas.create_rectangle(0, INTERSECTION_START, CANVAS_WIDTH, INTERSECTION_END, fill="gray20", outline="")
for i in range(0, int(INTERSECTION_START), 25):
    canvas.create_line(CENTER, i, CENTER, i + 15, fill="yellow", width=2, dash=(5,10))
    canvas.create_line(i, CENTER, i + 15, CENTER, fill="yellow", width=2, dash=(5,10))
for i in range(int(INTERSECTION_END) + 10, CANVAS_WIDTH, 25):
    canvas.create_line(CENTER, i, CENTER, i + 15, fill="yellow", width=2, dash=(5,10))
    canvas.create_line(i, CENTER, i + 15, CENTER, fill="yellow", width=2, dash=(5,10))
sl, el = INTERSECTION_START - STOP_LINE_MARGIN, INTERSECTION_END + STOP_LINE_MARGIN
canvas.create_line(INTERSECTION_START, sl, INTERSECTION_END, sl, fill="white", width=4)
canvas.create_line(INTERSECTION_START, el, INTERSECTION_END, el, fill="white", width=4)
canvas.create_line(sl, INTERSECTION_START, sl, INTERSECTION_END, fill="white", width=4)
canvas.create_line(el, INTERSECTION_START, el, INTERSECTION_END, fill="white", width=4)
post = canvas.create_rectangle(CENTER - 8, CENTER - 8, CENTER + 8, CENTER + 8, fill="black")
lights = {
    "North": canvas.create_oval(CENTER - 7, CENTER - 20, CENTER + 7, CENTER - 6, fill="red"),
    "South": canvas.create_oval(CENTER - 7, CENTER + 6, CENTER + 7, CENTER + 20, fill="red"),
    "East": canvas.create_oval(CENTER + 6, CENTER - 7, CENTER + 20, CENTER + 7, fill="red"),
    "West": canvas.create_oval(CENTER - 20, CENTER - 7, CENTER - 6, CENTER + 7, fill="red"),
}

# Create car pool
car_pool = {}
car_colors = ["#FF5733", "#33FF57", "#3357FF", "#F1C40F", "#9B59B6", "#1ABC9C", "#E74C3C", "#F39C12", "#D35400"]
for direction in directions:
    for lane_suffix in ["_L", "_R"]:
        lane_name = direction + lane_suffix
        car_pool[lane_name] = [Car(canvas, lane_name, random.choice(car_colors)) for _ in range(MAX_CARS_PER_LANE)]

# Create control frame
control_frame = tk.Frame(root, padx=10, pady=10)
control_frame.grid(row=0, column=1, rowspan=20, sticky="n")
tk.Label(control_frame, text="Simulation Control", font=("Arial", 16, "bold")).pack(pady=10, anchor="w")

# Add YOLO capture button
yolo_button = tk.Button(control_frame, text="Capture YOLO Input", width=15, command=start_yolo_capture)
yolo_button.pack(pady=5, fill="x")

pause_button = tk.Button(control_frame, text="Pause", width=12)
pause_button.pack(pady=5, fill="x")
tk.Label(control_frame, text="Time of Day:", font=("Arial", 12, "bold")).pack(pady=(10,0), anchor="w")
time_of_day_var = tk.StringVar(value="Normal")
for time_option in ["Normal", "Morning", "Evening"]:
    ttk.Radiobutton(control_frame, text=time_option, variable=time_of_day_var, value=time_option).pack(anchor="w")

tk.Label(control_frame, text="Time Tick Speed:", font=("Arial", 12, "bold")).pack(pady=(20,0), anchor="w")
speed_slider = ttk.Scale(control_frame, from_=1, to=10, orient="horizontal")
speed_slider.set(5)
speed_slider.pack(fill="x", pady=5)

# Info frame
info_frame = tk.Frame(control_frame, pady=10)
info_frame.pack(pady=10, fill="x")
tk.Label(info_frame, text="Active Direction:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w")
active_lane_label = tk.Label(info_frame, text="None", font=("Arial", 10), fg="green")
active_lane_label.grid(row=1, column=1, sticky="w")
tk.Label(info_frame, text="Time Left:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w")
time_left_label = tk.Label(info_frame, text="0s", font=("Arial", 10))
time_left_label.grid(row=2, column=1, sticky="w")

# Stats frame
stats_frame = tk.Frame(control_frame)
stats_frame.pack(pady=10, fill="x")
tk.Label(stats_frame, text="Direction", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w")
tk.Label(stats_frame, text="Cars", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=10)
tk.Label(stats_frame, text="Green (s)", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=10)
lane_labels = {}
for i, d in enumerate(directions):
    tk.Label(stats_frame, text=f"{d}:").grid(row=i+1, column=0, sticky="w")
    car_count_label = tk.Label(stats_frame, text="0")
    car_count_label.grid(row=i+1, column=1)
    duration_label = tk.Label(stats_frame, text="0s")
    duration_label.grid(row=i+1, column=2)
    lane_labels[d] = (car_count_label, duration_label)

# Detail frame
detail_frame = tk.Frame(control_frame, pady=10, relief="groove", borderwidth=2)
detail_frame.pack(pady=20, fill="x")
tk.Label(detail_frame, text="Simulation Details", font=("Arial", 12, "bold")).pack(anchor="w")
tk.Label(detail_frame, text="Total Cars Passed:", font=("Arial", 10)).pack(anchor="w", pady=2)
total_cars_label = tk.Label(detail_frame, text="0", font=("Arial", 10))
total_cars_label.pack(anchor="w")
tk.Label(detail_frame, text="Cars on Screen:", font=("Arial", 10)).pack(anchor="w", pady=2)
screen_cars_label = tk.Label(detail_frame, text="0", font=("Arial", 10))
screen_cars_label.pack(anchor="w")

# Initialize timing variables
last_time = time.time()
timer_countdown = 1.0
direction_timers = {direction: 0 for direction in directions}

def toggle_pause():
    global is_paused
    is_paused = not is_paused
    pause_button.config(text="Resume" if is_paused else "Pause")
pause_button.config(command=toggle_pause)

def pre_populate_cars():
    """Pre-populate lanes with cars based on traffic density"""
    if not current_traffic_counts: 
        return
    
    total_traffic = sum(current_traffic_counts.values())
    if total_traffic == 0:
        return
    
    for direction, count in current_traffic_counts.items():
        # Calculate how many cars to show based on traffic proportion (reduced number)
        traffic_proportion = count / total_traffic
        num_cars_to_show = int(8 * traffic_proportion)  # Reduced from 20 to 8 max per direction
        
        for lane_suffix in ["_L", "_R"]:
            lane_name = direction + lane_suffix
            cars_activated = 0
            
            for car in car_pool[lane_name]:
                if not car.is_active and cars_activated < num_cars_to_show // 2:
                    # Calculate position with proper spacing
                    if direction == "North":
                        lane_offset = 0 if "_L" in lane_name else -LANE_WIDTH
                        y_pos = -CAR_LENGTH - (cars_activated * (CAR_LENGTH + SAFE_DISTANCE))
                        car.activate(CENTER - LANE_WIDTH + lane_offset, y_pos)
                    elif direction == "South":
                        lane_offset = 0 if "_L" in lane_name else LANE_WIDTH
                        y_pos = CANVAS_HEIGHT + (cars_activated * (CAR_LENGTH + SAFE_DISTANCE))
                        car.activate(CENTER + lane_offset, y_pos)
                    elif direction == "West":
                        lane_offset = 0 if "_L" in lane_name else -LANE_WIDTH
                        x_pos = -CAR_LENGTH - (cars_activated * (CAR_LENGTH + SAFE_DISTANCE))
                        car.activate(x_pos, CENTER - LANE_WIDTH + lane_offset)
                    elif direction == "East":
                        lane_offset = 0 if "_L" in lane_name else LANE_WIDTH
                        x_pos = CANVAS_WIDTH + (cars_activated * (CAR_LENGTH + SAFE_DISTANCE))
                        car.activate(x_pos, CENTER + lane_offset)
                    
                    cars_activated += 1

def attempt_to_spawn_car():
    if not current_traffic_counts: return
    
    total_traffic = sum(current_traffic_counts.values())
    if total_traffic == 0:
        return
    
    current_time = time.time()
    
    for direction, count in current_traffic_counts.items():
        # Add delay between spawns for each direction
        if current_time - last_spawn_time[direction] < 0.5:  # 0.5 second delay
            continue
            
        # Higher spawn chance for high traffic directions
        traffic_proportion = count / total_traffic
        spawn_chance = 0.2 + (traffic_proportion * 0.3)  # 20-50% chance (reduced)
        
        if random.random() < spawn_chance:
            lane_suffix = random.choice(["_L", "_R"])
            lane_name = direction + lane_suffix
            
            # Find inactive car
            for car in car_pool[lane_name]:
                if not car.is_active:
                    car.activate()
                    last_spawn_time[direction] = current_time
                    break

def move_cars():
    if not simulation_started:
        return
        
    current_speed = BASE_CAR_SPEED * (speed_slider.get() / 5.0)
    
    for lane_name, car_list in car_pool.items():
        direction = lane_name.split("_")[0]
        is_green = canvas.itemcget(lights[direction], "fill") == "lime green"
        
        active_cars = [c for c in car_list if c.is_active]
        for i, car in enumerate(active_cars):
            move = True
            car_pos = car.get_front_pos()
            
            # Check distance to car in front
            if i > 0:
                car_in_front = active_cars[i-1]
                front_pos = car_in_front.get_front_pos()
                dist = abs(car_pos - front_pos)
                if dist < (CAR_LENGTH + SAFE_DISTANCE):
                    move = False
            
            # Update intersection status
            car.is_in_intersection = car.is_in_intersection_area()
            
            # Track if car has entered intersection
            if car.is_in_intersection and not car.has_entered_intersection:
                car.has_entered_intersection = True
            
            # FIXED: Cars that have entered intersection should always continue moving
            # until they exit the screen, regardless of timer or light status
            if car.has_entered_intersection:
                move = True
                car.waiting_at_light = False
            else:
                # Normal traffic light behavior for cars not yet in intersection
                if not is_green and car.is_at_stop_line():
                    car.waiting_at_light = True
                    move = False
                else:
                    car.waiting_at_light = False

            if car.is_past_intersection():
                car.has_passed_intersection = True

            if move:
                if car.direction == "North": car.move(0, current_speed)
                elif car.direction == "South": car.move(0, -current_speed)
                elif car.direction == "West": car.move(current_speed, 0)
                elif car.direction == "East": car.move(-current_speed, 0)

            if car.is_offscreen():
                car.deactivate()

def start_new_cycle():
    global active_direction_index, active_direction, time_left, current_durations
    
    for direction in directions:
        canvas.itemconfig(lights[direction], fill="red")
    
    active_direction_index = (active_direction_index + 1) % len(active_direction_sequence)
    active_direction = active_direction_sequence[active_direction_index]
    
    if active_direction_index == 0:
        current_durations = get_signal_durations(current_traffic_counts, time_of_day_var.get())
        
        for direction in directions:
            direction_timers[direction] = current_durations[direction]
        
        # PRE-POPULATE CARS based on new traffic values
        pre_populate_cars()

    time_left = current_durations[active_direction]
    
    canvas.itemconfig(lights[active_direction], fill="lime green")

    for d in directions:
        lane_labels[d][1].config(text=f"{current_durations.get(d, 0)}s")

def update_simulation():
    global time_left, last_time, timer_countdown
    if not is_paused and simulation_started:
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time
        timer_countdown -= delta_time * (speed_slider.get() / 5.0)

        if timer_countdown <= 0:
            if active_direction:
                direction_timers[active_direction] = max(0, direction_timers[active_direction] - 1)
            
            if time_left > 0:
                time_left -= 1
            else:
                start_new_cycle()
            timer_countdown = 1.0

        attempt_to_spawn_car()
        move_cars()
        
        active_lane_label.config(text=active_direction)
        time_left_label.config(text=f"{time_left}s")
        total_cars_label.config(text=str(total_cars_passed))
        screen_cars_label.config(text=str(cars_on_screen))

    root.after(20, update_simulation)

# Initialize with default values
current_durations = {d: 15 for d in directions}
for d in directions:
    direction_timers[d] = current_durations[d]

# Don't start the cycle automatically - wait for YOLO inputs
update_simulation()
root.mainloop()
