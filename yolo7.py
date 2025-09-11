import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading
import cv2
import numpy as np
import os
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from ultralytics import YOLO
from tkinter import font

# --- [ Original global variables and simulation logic remain unchanged ] ---

# Global variables
is_paused = False
active_direction = None
time_left = 0
current_traffic_counts = {}
current_durations = {}
total_cars_passed = 0
cars_on_screen = 0
yolo_inputs_received = {direction: False for direction in ["North", "South", "East", "West"]}
yolo_counts = {direction: [] for direction in ["North", "South", "East", "West"]}
yolo_processed_images = {direction: [] for direction in ["North", "South", "East", "West"]}
current_image_index = {direction: 0 for direction in ["North", "South", "East", "West"]}
cars_spawned_from_current_image = {direction: 0 for direction in ["North", "South", "East", "West"]}
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

# YOLO model initialization
YOLO_MODEL_PATH = r"C:\Python\traffic_images\yolov8n.pt"  # Using the default YOLOv8 nano model

# Directory for traffic images
TRAFFIC_IMAGE_DIR = r"C:\Python\traffic_images"
    
# Initialize YOLO model
try:
    yolo_model = YOLO(YOLO_MODEL_PATH, task='detect')
    print("YOLO model loaded successfully")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    yolo_model = None

# --- [ Car Class and Simulation Functions remain unchanged ] ---
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
        self.has_entered_intersection = False

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
        self.has_entered_intersection = False
        cars_on_screen += 1
        
        if x is None or y is None:
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

def process_image_with_yolo(direction, image_path):
    if yolo_model is None:
        messagebox.showerror("Error", "YOLO model failed to load. Using random counts instead.")
        return random.randint(5, 20), None
    
    try:
        image = cv2.imread(image_path)
        if image is None:
            messagebox.showerror("Error", f"Could not load image: {image_path}")
            return random.randint(5, 20), None
        
        results = yolo_model(image)
        vehicle_classes = [2, 3, 5, 7]
        vehicle_count = 0
        processed_image = image.copy()
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                if class_id in vehicle_classes:
                    vehicle_count += 1
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cv2.rectangle(processed_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        
        print(f"YOLO detected {vehicle_count} vehicles in {direction} direction from {os.path.basename(image_path)}")
        return vehicle_count, processed_image
        
    except Exception as e:
        messagebox.showerror("Error", f"YOLO processing failed: {str(e)}")
        return random.randint(5, 20), None

def capture_yolo_input(direction):
    current_image_index[direction] = 0
    cars_spawned_from_current_image[direction] = 0
    
    yolo_counts[direction] = []
    yolo_processed_images[direction] = []
    
    if not os.path.exists(TRAFFIC_IMAGE_DIR):
        os.makedirs(TRAFFIC_IMAGE_DIR)
        messagebox.showinfo("Info", f"Created {TRAFFIC_IMAGE_DIR} directory. Please add traffic images and try again.")
        yolo_inputs_received[direction] = True
        return
    
    image_files = []
    for file in os.listdir(TRAFFIC_IMAGE_DIR):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            if direction.lower() in file.lower():
                image_files.append(os.path.join(TRAFFIC_IMAGE_DIR, file))
    
    if not image_files:
        for file in os.listdir(TRAFFIC_IMAGE_DIR):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(TRAFFIC_IMAGE_DIR, file))
        if not image_files:
            messagebox.showerror("Error", f"No images found in {TRAFFIC_IMAGE_DIR} directory")
            yolo_counts[direction] = [random.randint(5, 20)]
            yolo_processed_images[direction] = [None]
            yolo_inputs_received[direction] = True
            return
    
    for image_path in image_files:
        count, processed_image = process_image_with_yolo(direction, image_path)
        yolo_counts[direction].append(count)
        yolo_processed_images[direction].append(processed_image)
    
    yolo_inputs_received[direction] = True
    
    if yolo_counts[direction]:
        lane_labels[direction][0].config(text=f"{yolo_counts[direction][0]}")

    if direction == yolo_view_direction.get():
        update_yolo_inspector_view()
    
    check_all_inputs_received()

def check_all_inputs_received():
    global simulation_started, current_traffic_counts
    
    if all(yolo_inputs_received.values()) and not simulation_started:
        simulation_started = True
        
        for direction in directions:
            if yolo_counts[direction]:
                current_traffic_counts[direction] = yolo_counts[direction][0]
            else:
                current_traffic_counts[direction] = random.randint(5, 20)

        pre_populate_cars()       
        start_new_cycle()
        messagebox.showinfo("Info", "All lane inputs received. Simulation starting!")

def start_yolo_capture():
    yolo_button.config(state=tk.DISABLED, text="Processing...")
    for direction in directions:
        yolo_inputs_received[direction] = False
        yolo_counts[direction] = []
        lane_labels[direction][0].config(text="0")
    
    def process_all_directions():
        for direction in directions:
            capture_yolo_input(direction)
        yolo_button.config(state=tk.NORMAL, text="Capture YOLO Input")

    thread = threading.Thread(target=process_all_directions)
    thread.daemon = True
    thread.start()

def pre_populate_cars():
    if not current_traffic_counts: return
    total_traffic = sum(current_traffic_counts.values())
    if total_traffic == 0: return
    
    for direction, count in current_traffic_counts.items():
        traffic_proportion = count / total_traffic
        num_cars_to_show = int(8 * traffic_proportion)
        
        for lane_suffix in ["_L", "_R"]:
            lane_name = direction + lane_suffix
            cars_activated = 0
            for car in car_pool[lane_name]:
                if not car.is_active and cars_activated < num_cars_to_show // 2:
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
                    cars_spawned_from_current_image[direction] += 1

def attempt_to_spawn_car():
    if not current_traffic_counts: return
    total_traffic = sum(current_traffic_counts.values())
    if total_traffic == 0: return
    current_time = time.time()
    
    for direction, count in current_traffic_counts.items():
        if cars_spawned_from_current_image[direction] >= count:
            if yolo_counts[direction] and len(yolo_counts[direction]) > 1:
                current_image_index[direction] = (current_image_index[direction] + 1) % len(yolo_counts[direction])
                current_traffic_counts[direction] = yolo_counts[direction][current_image_index[direction]]
                cars_spawned_from_current_image[direction] = 0
                if direction == yolo_view_direction.get():
                    update_yolo_inspector_view()
            continue
        if current_time - last_spawn_time[direction] < 0.5: continue
        traffic_proportion = count / total_traffic
        spawn_chance = 0.2 + (traffic_proportion * 0.3)
        if random.random() < spawn_chance:
            lane_suffix = random.choice(["_L", "_R"])
            lane_name = direction + lane_suffix
            for car in car_pool[lane_name]:
                if not car.is_active:
                    car.activate()
                    last_spawn_time[direction] = current_time
                    cars_spawned_from_current_image[direction] += 1
                    break

def move_cars():
    if not simulation_started: return
    current_speed = BASE_CAR_SPEED * (speed_slider.get() / 5.0)
    
    for lane_name, car_list in car_pool.items():
        direction = lane_name.split("_")[0]
        is_green = canvas.itemcget(lights[direction], "fill") == "lime green"
        
        active_cars = [c for c in car_list if c.is_active]
        for i, car in enumerate(active_cars):
            move = True
            car_pos = car.get_front_pos()
            
            if i > 0:
                car_in_front = active_cars[i-1]
                front_pos = car_in_front.get_front_pos()
                dist = abs(car_pos - front_pos)
                if dist < (CAR_LENGTH + SAFE_DISTANCE): move = False
            
            car.is_in_intersection = car.is_in_intersection_area()
            if car.is_in_intersection and not car.has_entered_intersection: car.has_entered_intersection = True
            
            if car.has_entered_intersection:
                move = True
                car.waiting_at_light = False
            else:
                if not is_green and car.is_at_stop_line():
                    car.waiting_at_light = True
                    move = False
                else: car.waiting_at_light = False

            if car.is_past_intersection(): car.has_passed_intersection = True

            if move:
                if car.direction == "North": car.move(0, current_speed)
                elif car.direction == "South": car.move(0, -current_speed)
                elif car.direction == "West": car.move(current_speed, 0)
                elif car.direction == "East": car.move(-current_speed, 0)

            if car.is_offscreen(): car.deactivate()

def start_new_cycle():
    global active_direction_index, active_direction, time_left, current_durations
    for direction in directions: canvas.itemconfig(lights[direction], fill="red")
    active_direction_index = (active_direction_index + 1) % len(active_direction_sequence)
    active_direction = active_direction_sequence[active_direction_index]
    
    if active_direction_index == 0:
        # --- MODIFICATION: Hardcoded "Normal" since the GUI option was removed ---
        current_durations = get_signal_durations(current_traffic_counts, "Normal")
        for direction in directions: direction_timers[direction] = current_durations[direction]

    time_left = current_durations[active_direction]
    canvas.itemconfig(lights[active_direction], fill="lime green")
    for d in directions: lane_labels[d][1].config(text=f"{current_durations.get(d, 0)}s")

def update_simulation():
    global time_left, last_time, timer_countdown
    if not is_paused and simulation_started:
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time
        timer_countdown -= delta_time * (speed_slider.get() / 5.0)

        if timer_countdown <= 0:
            if active_direction: direction_timers[active_direction] = max(0, direction_timers[active_direction] - 1)
            if time_left > 0: time_left -= 1
            else: start_new_cycle()
            timer_countdown = 1.0

        attempt_to_spawn_car()
        move_cars()
        
        active_lane_label.config(text=str(active_direction))
        time_left_label.config(text=f"{time_left}s")
        total_cars_label.config(text=str(total_cars_passed))
        screen_cars_label.config(text=str(cars_on_screen))

    root.after(20, update_simulation)


# --- [ GUI SECTION ] ---

# Create the main window
root = tk.Tk()
root.title("YOLO Integrated Traffic Simulation")
root.geometry("1250x850") # Set a default size

# Define fonts
TITLE_FONT = font.Font(family="Arial", size=14, weight="bold")
LABEL_FONT = font.Font(family="Arial", size=10)
BOLD_LABEL_FONT = font.Font(family="Arial", size=10, weight="bold")

# Configure grid layout
root.grid_columnconfigure(0, weight=3) # Canvas column
root.grid_columnconfigure(1, weight=1) # Control panel column
root.grid_rowconfigure(0, weight=1)

# --- Simulation Canvas ---
canvas = tk.Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#4F4F4F")
canvas.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

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

# --- Main Control Panel ---
main_control_frame = ttk.Frame(root, padding=10)
main_control_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

# --- Simulation Control Section ---
control_labelframe = ttk.LabelFrame(main_control_frame, text="Simulation Control", padding=10)
control_labelframe.pack(fill="x", pady=(0, 10))

yolo_button = ttk.Button(control_labelframe, text="Capture YOLO Input", command=start_yolo_capture)
yolo_button.pack(fill="x", pady=5)

pause_button = ttk.Button(control_labelframe, text="Pause")
pause_button.pack(fill="x", pady=5)

ttk.Separator(control_labelframe, orient='horizontal').pack(fill='x', pady=10)

# --- MODIFICATION: "Time of Day" radio buttons have been removed ---

ttk.Label(control_labelframe, text="Time Tick Speed:", font=BOLD_LABEL_FONT).pack(anchor="w", pady=(5,2))
speed_slider = ttk.Scale(control_labelframe, from_=1, to=10, orient="horizontal")
speed_slider.set(5)
speed_slider.pack(fill="x", pady=5)


# --- Real-time Stats Section ---
stats_labelframe = ttk.LabelFrame(main_control_frame, text="Real-time Stats", padding=10)
stats_labelframe.pack(fill="x", pady=10)
stats_labelframe.grid_columnconfigure(1, weight=1)
stats_labelframe.grid_columnconfigure(2, weight=1)

# Active Direction and Time Left
info_frame = ttk.Frame(stats_labelframe)
info_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 10))
ttk.Label(info_frame, text="Active Direction:", font=BOLD_LABEL_FONT).pack(side='left')
active_lane_label = ttk.Label(info_frame, text="None", font=LABEL_FONT, foreground="green")
active_lane_label.pack(side='left', padx=5)
time_left_label = ttk.Label(info_frame, text="0s", font=LABEL_FONT)
time_left_label.pack(side='right', padx=5)
ttk.Label(info_frame, text="Time Left:", font=BOLD_LABEL_FONT).pack(side='right')

# Stats Headers
ttk.Label(stats_labelframe, text="Direction", font=BOLD_LABEL_FONT).grid(row=1, column=0, sticky="w")
ttk.Label(stats_labelframe, text="Cars", font=BOLD_LABEL_FONT).grid(row=1, column=1)
ttk.Label(stats_labelframe, text="Green (s)", font=BOLD_LABEL_FONT).grid(row=1, column=2)

# Per-direction stats
lane_labels = {}
for i, d in enumerate(directions):
    ttk.Label(stats_labelframe, text=f"{d}:").grid(row=i+2, column=0, sticky="w", pady=2)
    car_count_label = ttk.Label(stats_labelframe, text="0", anchor="center")
    car_count_label.grid(row=i+2, column=1, sticky='ew')
    duration_label = ttk.Label(stats_labelframe, text="0s", anchor="center")
    duration_label.grid(row=i+2, column=2, sticky='ew')
    lane_labels[d] = (car_count_label, duration_label)

# --- Simulation Details ---
details_labelframe = ttk.LabelFrame(main_control_frame, text="Simulation Details", padding=10)
details_labelframe.pack(fill="x", pady=10)
ttk.Label(details_labelframe, text="Total Cars Passed:", font=BOLD_LABEL_FONT).grid(row=0, column=0, sticky='w')
total_cars_label = ttk.Label(details_labelframe, text="0", font=LABEL_FONT)
total_cars_label.grid(row=0, column=1, sticky='w', padx=5)
ttk.Label(details_labelframe, text="Cars on Screen:", font=BOLD_LABEL_FONT).grid(row=1, column=0, sticky='w')
screen_cars_label = ttk.Label(details_labelframe, text="0", font=LABEL_FONT)
screen_cars_label.grid(row=1, column=1, sticky='w', padx=5)


# --- YOLO Image Inspector ---
yolo_inspector_frame = ttk.LabelFrame(main_control_frame, text="YOLO Image Inspector", padding=10)
yolo_inspector_frame.pack(fill="both", expand=True, pady=10)

# Dropdown to select direction
yolo_view_direction = tk.StringVar(value=directions[0])
direction_selector = ttk.Combobox(yolo_inspector_frame, textvariable=yolo_view_direction, values=directions, state='readonly')
direction_selector.pack(fill='x', pady=(0, 5))

# Frame to hold the Matplotlib canvas
image_display_frame = ttk.Frame(yolo_inspector_frame, relief="sunken", borderwidth=1)
image_display_frame.pack(fill="both", expand=True, pady=5)
current_displayed_image_canvas = None

# Navigation controls for images
nav_frame = ttk.Frame(yolo_inspector_frame)
nav_frame.pack(fill='x', pady=(5, 0))
nav_frame.grid_columnconfigure(1, weight=1)

prev_btn = ttk.Button(nav_frame, text="< Prev")
prev_btn.grid(row=0, column=0)
image_info_label = ttk.Label(nav_frame, text="No Images", anchor='center')
image_info_label.grid(row=0, column=1, sticky='ew')
next_btn = ttk.Button(nav_frame, text="Next >")
next_btn.grid(row=0, column=2)

def display_processed_image(direction, image_index):
    global current_displayed_image_canvas
    if current_displayed_image_canvas:
        current_displayed_image_canvas.get_tk_widget().destroy()

    if not yolo_processed_images[direction] or image_index >= len(yolo_processed_images[direction]):
        image_info_label.config(text=f"{direction}: No Images")
        return
    
    processed_image = yolo_processed_images[direction][image_index]
    if processed_image is None:
        image_info_label.config(text=f"{direction}: Image {image_index+1} Error")
        return

    processed_image_rgb = cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB)
    
    fig = plt.Figure(figsize=(4, 3), dpi=80)
    ax = fig.add_subplot(111)
    ax.imshow(processed_image_rgb)
    ax.axis('off')
    fig.tight_layout(pad=0)
    
    current_displayed_image_canvas = FigureCanvasTkAgg(fig, master=image_display_frame)
    current_displayed_image_canvas.draw()
    current_displayed_image_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    total_images = len(yolo_processed_images[direction])
    count = yolo_counts[direction][image_index]
    image_info_label.config(text=f"{direction}: {count} cars (Image {image_index+1}/{total_images})")

def update_yolo_inspector_view(*args):
    direction = yolo_view_direction.get()
    idx = current_image_index[direction]
    display_processed_image(direction, idx)

def show_next_image():
    direction = yolo_view_direction.get()
    if not yolo_processed_images[direction]: return
    current_image_index[direction] = (current_image_index[direction] + 1) % len(yolo_processed_images[direction])
    update_yolo_inspector_view()

def show_previous_image():
    direction = yolo_view_direction.get()
    if not yolo_processed_images[direction]: return
    current_image_index[direction] = (current_image_index[direction] - 1) % len(yolo_processed_images[direction])
    update_yolo_inspector_view()

# Bind commands to new widgets
yolo_view_direction.trace_add("write", update_yolo_inspector_view)
next_btn.config(command=show_next_image)
prev_btn.config(command=show_previous_image)

def toggle_pause():
    global is_paused
    is_paused = not is_paused
    pause_button.config(text="Resume" if is_paused else "Pause")
pause_button.config(command=toggle_pause)

# --- Car Pool Creation and Final Setup ---
car_pool = {}
car_colors = ["#FF5733", "#33FF57", "#3357FF", "#F1C40F", "#9B59B6", "#1ABC9C", "#E74C3C", "#F39C12", "#D35400"]
for direction in directions:
    for lane_suffix in ["_L", "_R"]:
        lane_name = direction + lane_suffix
        car_pool[lane_name] = [Car(canvas, lane_name, random.choice(car_colors)) for _ in range(MAX_CARS_PER_LANE)]

# Initialize timing variables
last_time = time.time()
timer_countdown = 1.0
direction_timers = {direction: 0 for direction in directions}
current_durations = {d: 15 for d in directions}
for d in directions:
    direction_timers[d] = current_durations[d]

# Start simulation loop
update_yolo_inspector_view() # Initial image display
update_simulation()
root.mainloop()
