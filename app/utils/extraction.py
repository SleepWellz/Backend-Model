import re
import random

def normalize_time(t):
    parts = t.split(":")
    return ":".join(part.zfill(2) for part in parts)

def time_to_seconds(time_str):
    h, m, s = map(int, time_str.split(":"))
    return h * 3600 + m * 60 + s

def get_segments_from_range(start_time: int, end_time: int, segment_length=5, hop=1):
    segments = []
    for t in range(start_time, end_time - segment_length + 1, hop):
        segments.append((t, t + segment_length))
    return segments

def find_s2_notation(txt_path):
    s2_times = []
    with open(txt_path, 'r') as file:
        for line in file:
            if "S2" in line:
                match = re.search(r'\b(\d{0,2}):(\d{0,2}):(\d{0,2})\b', line)
                if match:
                    hour, minute, second = map(int, match.groups())
                    if hour < 8:
                        formatted_time = f"{str(hour).zfill(2)}:{str(minute).zfill(2)}:{str(second).zfill(2)}"
                        s2_times.append(formatted_time)

    if s2_times:
        start_time = time_to_seconds(random.choice(s2_times))
        end_time = int(start_time) + 15
        print(f"Random S2 timestamp: {start_time}")
        print(f"Random S2 timestamp: {end_time}")
        return get_segments_from_range(start_time, end_time)
    else:
        print("No 'S2' entries with valid timestamps found.")
        return None