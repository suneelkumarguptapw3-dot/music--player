import subprocess
import random
import re
import json

video = "4VwtfInG-LU.webm"
output = "out3.webm"
samples = 10

# Get video dimensions and duration
info = subprocess.run([
    "ffprobe", "-v", "error",
    "-select_streams", "v:0",
    "-show_entries", "stream=width,height:format=duration",
    "-of", "json", video
], capture_output=True, text=True, check=True)

data = json.loads(info.stdout)
stream = data["streams"][0]
width, height = stream["width"], stream["height"]
duration = float(data["format"]["duration"])

# Random timestamps
timestamps = [
    random.uniform(0, max(0, duration - 0.1))
    for _ in range(samples)
]

# Detect dark rows from each sampled frame
tops = []
bottoms = []

for t in timestamps:
    p = subprocess.run([
        "ffmpeg", "-v", "error",
        "-ss", str(t), "-i", video,
        "-frames:v", "1",
        "-vf", "format=gray",
        "-f", "rawvideo", "-"
    ], capture_output=True, check=True)

    frame = p.stdout
    if len(frame) != width * height:
        print(f"{t:.1f}s: invalid frame")
        continue

    # A row is dark if at least 98% of pixels have brightness <= 25.
    row_dark = []
    for y in range(height):
        row = frame[y * width:(y + 1) * width]
        dark = sum(v <= 25 for v in row)
        row_dark.append(dark >= width * 0.98)

    # Count consecutive dark rows from top
    top = 0
    while top < height // 2 and row_dark[top]:
        top += 1

    # Count consecutive dark rows from bottom
    bottom = height
    while bottom > height // 2 and row_dark[bottom - 1]:
        bottom -= 1

    tops.append(top)
    bottoms.append(bottom)

    print(f"{t:.1f}s: top={top}px, bottom bar={height-bottom}px")

if not tops:
    raise RuntimeError("No frames could be analyzed.")

# Conservative crop: remove bars only when supported by the samples.
top = min(tops)
bottom = max(bottoms)

# Keep even dimensions and offsets
top = (top // 2) * 2
crop_height = ((bottom - top) // 2) * 2

if crop_height <= 0:
    raise RuntimeError("Invalid crop dimensions.")

# Centre crop in X direction to make the output square
crop_width = min(width, crop_height)
crop_width = (crop_width // 2) * 2
left = ((width - crop_width) // 2) // 2 * 2

# Ensure square dimensions
crop_height = crop_width

# Ensure the vertical crop remains within the detected bar-free area
if crop_height > bottom - top:
    raise RuntimeError("Not enough height available for a square crop.")

print(f"Final crop: {crop_width}:{crop_height}:{left}:{top}")

subprocess.run([
    "ffmpeg", "-hide_banner", "-y",
    "-i", video,
    "-vf", f"crop={crop_width}:{crop_height}:{left}:{top}",
    "-c:v", "libvpx",
    "-deadline", "realtime",
    "-cpu-used", "8",
    "-threads", "4",
    "-crf", "30",
    "-b:v", "0",
    "-c:a", "copy",
    output
], check=True)

print("Saved:", output)