# Authors: Dhanuj Gandikota
import os
import time
import threading
import sounddevice as sd
import numpy as np
import wave
from datetime import datetime, timedelta
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
import csv
from threading import Lock
import requests
import urllib.parse

# Constants
OUTPUT_FOLDER = '/home/keittlab/Documents/birdnet-lite-demo/output_test'
LEDGER_FILE = os.path.join(OUTPUT_FOLDER, 'ledger.csv')
LAT = 30.2672  # Austin, Texas latitude
LON = -97.7431  # Austin, Texas longitude

CHUNK_DURATION = 20  # seconds
BUFFER_SIZE = 2  # Number of chunks to combine (2 x 20s = 40s)
SAMPLE_RATE = 44100  # Hz - Yeti Mic
#SAMPLE_RATE = 48000  # Hz - Umi Mic
CHANNELS = 4
MAX_RECORDINGS = 5

# Device Index (to be updated after identifying the correct device)
DEVICE_INDEX = None  # Will set this after querying devices

# Global variables for tracking analyzed recordings and bird images
analyzed_recordings = []
analyzed_recordings_lock = Lock()
previous_scientific_name = None  # To keep track of the previous scientific name
previous_scientific_name_lock = Lock()

def record_audio(duration, sample_rate, channels, device=None):
    """Record audio for a given duration and return as a NumPy array."""
    print(f"Recording audio for {duration} seconds on device {device}...")
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype='int16',
        device=device,
    )
    sd.wait()
    return recording

def save_wav_file(filename, data, sample_rate):
    """Save NumPy array data to a WAV file."""
    print(f"Saving WAV file to {filename}...")
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16 bits = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

def analyze_recording(analyzer, wav_file, timestamp):
    """Analyze the WAV file using birdnetlib."""
    print(f"Analyzing {wav_file}...")
    date_obj = datetime.fromtimestamp(timestamp)
    recording = Recording(
        analyzer,
        wav_file,
        lat=LAT,
        lon=LON,
        date=date_obj,
        min_conf=0.25
    )
    recording.analyze()
    return recording.detections

def update_ledger_and_fetch_image(detections, timestamp):
    """Update the ledger.csv file with detections and fetch bird images."""
    print("Updating ledger...")
    date_obj = datetime.fromtimestamp(timestamp)
    date_str = date_obj.strftime('%Y-%m-%d')
    start_time_str = date_obj.strftime('%H:%M:%S')
    end_time_obj = date_obj + timedelta(seconds=CHUNK_DURATION * BUFFER_SIZE)
    end_time_str = end_time_obj.strftime('%H:%M:%S')

    # Check if ledger file exists
    file_exists = os.path.isfile(LEDGER_FILE)

    global previous_scientific_name
    new_scientific_name = None

    with open(LEDGER_FILE, 'a', newline='') as csvfile:
        fieldnames = ["date", "start_Time", "end_Time", "lat", "lon", "label", "scientific_name", "confidence"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header if file does not exist
        if not file_exists:
            writer.writeheader()

        for detection in detections:
            common_name = detection.get('common_name', '')
            scientific_name = detection.get('scientific_name', '')
            confidence = detection.get('confidence', '')

            writer.writerow({
                "date": date_str,
                "start_Time": start_time_str,
                "end_Time": end_time_str,
                "lat": LAT,
                "lon": LON,
                "label": common_name,
                "scientific_name": scientific_name,
                "confidence": confidence
            })

            # Check if the scientific name is different from the previous one
            with previous_scientific_name_lock:
                if scientific_name and scientific_name != previous_scientific_name:
                    new_scientific_name = scientific_name
                    previous_scientific_name = scientific_name
                    break  # Only fetch image for the first new scientific name

    # Fetch image for the new scientific name
    if new_scientific_name:
        fetch_and_save_bird_image(new_scientific_name)

def fetch_and_save_bird_image(scientific_name):
    """Fetch the first bird image from Wikimedia Commons and save it."""
    print(f"Fetching image for new bird: {scientific_name}")

    # URL encode the scientific name
    encoded_name = urllib.parse.quote(scientific_name)
    # Construct the search URL with gsrnamespace=6 to search in File namespace
    search_url = (
        "https://commons.wikimedia.org/w/api.php?"
        "action=query&format=json&prop=imageinfo&generator=search&"
        f"gsrsearch={encoded_name}&gsrnamespace=6&gsrlimit=1&"
        "iiprop=url|mime&iiurlwidth=500"
    )

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; BirdImageFetcher/1.0)'
    }

    try:
        response = requests.get(search_url, headers=headers)
        data = response.json()
        # Uncomment the next line to debug API responses
        # print(f"API response data: {data}")
        pages = data.get('query', {}).get('pages', {})
        if pages:
            for page in pages.values():
                imageinfo = page.get('imageinfo', [{}])[0]
                # Use 'thumburl' to get the thumbnail URL
                image_url = imageinfo.get('thumburl')
                if image_url:
                    print(f"Image URL: {image_url}")
                    # Attempt to download the image
                    image_response = requests.get(image_url, headers=headers, allow_redirects=True)
                    print(f"Image download status code: {image_response.status_code}")
                    if image_response.status_code == 200:
                        # Save the image as current_bird.png
                        image_path = os.path.join(OUTPUT_FOLDER, 'current_bird.png')
                        with open(image_path, 'wb') as img_file:
                            img_file.write(image_response.content)
                        print(f"Saved image for {scientific_name} as current_bird.png")
                    else:
                        print(f"Failed to download image for {scientific_name}. HTTP status code: {image_response.status_code}")
                else:
                    print(f"No image URL found for {scientific_name}")
        else:
            print(f"No images found for {scientific_name}")
    except Exception as e:
        print(f"Error fetching image for {scientific_name}: {e}")

def analyze_and_update(analyzer, wav_file, timestamp):
    """Analyze the recording, update the ledger, and manage recordings."""
    detections = analyze_recording(analyzer, wav_file, timestamp)
    update_ledger_and_fetch_image(detections, timestamp)

    # Now delete old recordings if necessary
    with analyzed_recordings_lock:
        analyzed_recordings.append(wav_file)
        if len(analyzed_recordings) > MAX_RECORDINGS:
            oldest_wav_file = analyzed_recordings.pop(0)
            if os.path.exists(oldest_wav_file):
                os.remove(oldest_wav_file)
                print(f"Deleted old recording {oldest_wav_file}")

def delete_existing_files():
    """Delete all .wav and .csv files in the output folder."""
    print(f"Deleting existing .wav and .csv files in {OUTPUT_FOLDER}...")
    for filename in os.listdir(OUTPUT_FOLDER):
        if filename.endswith('.wav') or filename.endswith('.csv'):
            file_path = os.path.join(OUTPUT_FOLDER, filename)
            try:
                os.remove(file_path)
                print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

def main():
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # User option to delete existing files
    delete_choice = input("Do you want to delete all existing .wav and .csv files in the output folder before starting? (y/n): ").strip().lower()
    if delete_choice == 'y':
        delete_existing_files()
    elif delete_choice == 'n':
        print("Existing files will be kept.")
    else:
        print("Invalid input. Existing files will be kept.")

    # Initialize BirdNET analyzer
    print("Loading BirdNET model (this may take a moment)...")
    analyzer = Analyzer()

    # Identify audio devices
    devices = sd.query_devices()
    print("Available audio devices:")
    for idx, device in enumerate(devices):
        print(f"{idx}: {device['name']} ({device['max_input_channels']} in, {device['max_output_channels']} out)")

    # Set the DEVICE_INDEX after identifying your device
    global DEVICE_INDEX
    DEVICE_INDEX = int(input("Enter the device index for your microphone: "))

    audio_buffer = []
    timestamps = []

    while True:
        # Record audio chunk
        chunk = record_audio(CHUNK_DURATION, SAMPLE_RATE, CHANNELS, device=DEVICE_INDEX)
        timestamp = time.time()

        # Append chunk and timestamp to buffers
        audio_buffer.append(chunk)
        timestamps.append(timestamp)

        # Keep only the last BUFFER_SIZE chunks
        if len(audio_buffer) > BUFFER_SIZE:
            audio_buffer.pop(0)
            timestamps.pop(0)

        # If we have enough chunks, save and process
        if len(audio_buffer) == BUFFER_SIZE:
            # Combine chunks
            combined_audio = np.concatenate(audio_buffer)
            # Use the timestamp of the first chunk as the start time
            start_timestamp = timestamps[0]
            date_obj = datetime.fromtimestamp(start_timestamp)
            filename = date_obj.strftime('%Y%m%d_%H%M%S.wav')
            wav_file_path = os.path.join(OUTPUT_FOLDER, filename)

            # Save WAV file
            save_wav_file(wav_file_path, combined_audio, SAMPLE_RATE)

            # Start a new thread to analyze the recording
            analysis_thread = threading.Thread(target=analyze_and_update, args=(analyzer, wav_file_path, start_timestamp))
            analysis_thread.start()

        # Recording takes CHUNK_DURATION time, so no need to sleep

if __name__ == '__main__':
    main()
