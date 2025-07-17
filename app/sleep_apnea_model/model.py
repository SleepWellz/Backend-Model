
import mne
import numpy as np
import tensorflow as tf
from scipy.fft import fft
from scipy.signal import find_peaks
import pandas as pd
import random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import datetime
import base64

global_models = {
    # "CNN": tf.keras.models.load_model("app/sleep_apnea_model/model/CNN.h5"),
    # "CNN": tf.keras.models.load_model("app/sleep_apnea_model/model/CNN FINAL.h5"),
    # "CNN": tf.keras.models.load_model("app/sleep_apnea_model/model/test/1d cnn 70.h5"),
    "CNN": tf.keras.models.load_model("app/sleep_apnea_model/model/test/1d cnn 70.h5"),
    "LSTM": tf.keras.models.load_model("app/sleep_apnea_model/model/test/lstm 70.h5")
}

channel_names = ["TERMISTORE", "TORACE", "ADDOME", "SpO2"]
class_labels = ["apnea", "normal"]
fixed_channel_names = ["Flow", "Sum", "abdo", "SpO2"]

def channels_check(raw):
    used_channels = fixed_channel_names
    missing = [ch for ch in fixed_channel_names if ch not in raw.ch_names]
    if missing:
        used_channels = channel_names
    missing = [ch for ch in used_channels if ch not in raw.ch_names]
    if missing:
        return None, "no eligible channels"
    return used_channels, None

def load_signal(signal, cnn):
    try:
        raw = mne.io.read_raw_edf(signal, preload=True)
        resampled = raw.copy()
        fs = raw.info['sfreq']
        if fs > 8 and cnn:
            resampled.resample(8, npad="auto")
            fs = 8
            print(f"Downsampled to: {fs}Hz")
        # if fs > 128:
        #     resampled.resample(128, npad="auto")
        #     fs = 128
        #     print(f"Downsampled to: {fs}Hz")
        return raw, resampled, None
    except Exception as e:
        return None, None, str(e)
def toFFT(samples):
    fft_data = []

    for sample in samples:
        sample_fft = fft(sample, axis=0)
        sample_fft = sample_fft.real.astype(np.float32)
        fft_data.append(sample_fft)

    fft_data = np.array(fft_data)
    fft_data = np.expand_dims(fft_data, axis=-1)

    print("toFFT done, new shape:", fft_data.shape)

    return fft_data

def trim_signal(raw, start_time, end_time, used_channels):
    # raw = mne.io.read_raw_edf(signal, preload=True)
    fs = int(raw.info['sfreq'])
    print("trimming signals")
    trimmed_signals = {}
    raw = raw.copy()
    raw.crop(tmin=start_time, tmax=end_time)

    for ch in used_channels:
        if ch in raw.ch_names:
            data = raw.copy().pick([ch])
            print(f"channel name: {ch}")
            print("loop before checking spo2 flow")
            if ch == "SpO2" or ch == "Flow":
                data = data.get_data()[0]
                data = np.clip(data, 0, 200)
                data = (data - np.min(data)) / (np.max(data) - np.min(data)) * 100
                data = np.round(data).astype(np.int16)

                info = mne.create_info([ch], sfreq=fs, ch_types="misc")
                data = mne.io.RawArray(data.reshape(1, -1), info)

            print("after checking spo2 flow")
            trimmed_signals[ch] = data.get_data()[0]
        else:
            print(f"Channel {ch} not found in EDF file.")

    print("finish trimming")
    return trimmed_signals, fs

def combine_signal(stacked_signal, fs, start_time, end_time):
    print("combining signals")
    combined_signal = np.vstack([stacked_signal[ch] for ch in stacked_signal if stacked_signal[ch] is not None])
    if combined_signal.shape[0] == 0:
        print("Error: No valid signals found for combination.")
        return None

    ch_names = list(stacked_signal.keys())
    info = mne.create_info(ch_names=ch_names, sfreq=fs, ch_types="misc")
    combined_raw = mne.io.RawArray(combined_signal, info)
    combined_file = f"raw_{start_time}-{end_time}.edf"
    mne.export.export_raw(combined_file, combined_raw, fmt="edf", overwrite=True)

    return combined_file

def reshape_signals(X):
    return X.reshape((X.shape[0], X.shape[1], X.shape[2]))

def preprocess_with_trim(raw_signal, fft, start_time, end_time, used_channels):
    # fft = True
    stacked_signal, fs = trim_signal(raw_signal, start_time, end_time, used_channels)
    signal_data = combine_signal(stacked_signal, fs, start_time, end_time)

    processed_signal = signal_data
    processed_signal = mne.io.read_raw_edf(processed_signal, preload=True)
    print(f"channels: {processed_signal.ch_names}")
    processed_signal = processed_signal.get_data()
    print(f"shape: {processed_signal.shape}")

    processed_signal = np.nan_to_num(processed_signal, nan=0.0, posinf=1.0, neginf=-1.0)

    min_val = np.min(processed_signal, axis=1, keepdims=True)
    max_val = np.max(processed_signal, axis=1, keepdims=True)
    processed_signal = (processed_signal - min_val) / (max_val - min_val + 1e-8)

    processed_signal = processed_signal.T
    processed_signal = np.expand_dims(processed_signal, axis=0)

    processed_signal = np.array(processed_signal, dtype=np.float32)
    print(f"before reshape: {processed_signal.shape}")
    # if fft:
    #     processed_signal = toFFT(processed_signal)

    processed_signal = reshape_signals(processed_signal)
    print(f"after reshape: {processed_signal.shape}")

    return processed_signal, signal_data


def preprocess(file, fft, model_type):
    signal_data = mne.io.read_raw_edf(file, preload=True)
    signal_data = signal_data.get_data()

    signal_data = np.nan_to_num(signal_data, nan=0.0, posinf=1.0, neginf=-1.0)

    min_val = np.min(signal_data, axis=1, keepdims=True)
    max_val = np.max(signal_data, axis=1, keepdims=True)
    signal_data = (signal_data - min_val) / (max_val - min_val + 1e-8)

    signal_data = signal_data.T
    signal_data = np.expand_dims(signal_data, axis=0)

    signal_data = np.array(signal_data, dtype=np.float32)
    signal_data = reshape_signals(signal_data, model_type)
    if fft:
        signal_data = toFFT(signal_data)

    return signal_data

def predict(processed_signal, model_type):
    # tf.keras.backend.clear_session()
    # model = tf.keras.models.load_model(model_path)
    model = global_models[model_type]
    prediction = model.predict(processed_signal)
    if prediction.shape[-1] == 1:
        predicted_class = int(prediction[0][0] >= 0.5)
    else:
        predicted_class = np.argmax(prediction)
    print(f"Predicted Class: {class_labels[predicted_class]}\n")

    return class_labels[predicted_class]

def convert_csv_to_edf_selected_channels(file_path, sfreq=64, output_path="selected_channels.edf"):
    try:
        df = pd.read_csv(file_path)
        # missing = [ch for ch in channel_names if ch not in df.columns]
        missing = [ch for ch in fixed_channel_names if ch not in df.columns]
        if missing:
            return None, f"Missing channels in CSV: {missing}"
        # df[fixed_channel_names] = df[fixed_channel_names] * 1000015
        data = df[fixed_channel_names].to_numpy().T
        info = mne.create_info(ch_names=fixed_channel_names, sfreq=sfreq, ch_types='misc')
        raw = mne.io.RawArray(data, info)
        mne.export.export_raw(output_path, raw, fmt="edf", overwrite=True)

        return output_path, None
    except Exception as e:
        return None, f"Conversion failed: {e}"

def find_non_annotatated_segments(edf_file):
    try:
        raw = mne.io.read_raw_edf(edf_file, preload=False)
        duration = raw.times[-1]

        if duration < 15:
            return None, f"EDF file is too short ({duration:.2f}s) for a 15-second segment."

        max_start_time = duration - 15
        start_time = random.uniform(0, max_start_time)

        return round(start_time, 2), None

    except Exception as e:
        return None, f"Error loading EDF file: {e}"

def duration_check(edf_file):
    try:
        raw = mne.io.read_raw_edf(edf_file, preload=False)
        duration = raw.times[-1]
        if duration < 60.60:
            return None, f"EDF file is too short ({duration:.2f}s). Minimum recording duration is 90 minutes"
        return duration, None

    except Exception as e:
        return None, f"Error loading EDF file: {e}"
    
def check_oxygen_desaturation(raw, start_time):
    try:
        # raw = mne.io.read_raw_edf(edf_file, preload=True)
        sfreq = int(raw.info["sfreq"])
        
        spo2_data = raw.copy().pick_channels(["SpO2"]).get_data()[0]

        start_idx = start_time * sfreq
        end_idx = (start_time + 11) * sfreq

        segment = spo2_data[start_idx:end_idx]
        min_value = np.min(segment)

        return min_value
    except Exception as e:
        return f"{e}"
    
def visualize_segment(raw, current_user_id, start_time, min_spo2, used_channels):
    try:
        print("visualizing segment")
        # raw = mne.io.read_raw_edf(edf_file, preload=True)

        end_time = start_time + 10
        start_time = start_time - 110

        raw.pick_channels(used_channels)
        raw_segment = raw.copy().crop(start_time, end_time)
        data = raw_segment.get_data()
        num_samples = data.shape[1]
        x = np.linspace(start_time, end_time, num_samples)

        timestamp = int(datetime.datetime.now().timestamp())
        save_path = f"app/visualized_signals/{current_user_id}-{timestamp}-{start_time}-{end_time}.png"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Plotting
        plt.figure(figsize=(12, 8))
        y_margin = 3  # atau sesuaikan sesuai keinginanmu
        for i, channel in enumerate(used_channels):
            plt.subplot(len(used_channels), 1, i + 1)
            plt.plot(x, data[i], color=f'C{i}')
            plt.title(channel, fontsize=10)
            plt.xlabel("Time (seconds)")
            plt.ylabel("Amplitude")
            plt.grid(True)
            
            # Ambil nilai minimum dan maksimum channel
            ch_min = np.min(data[i])
            ch_max = np.max(data[i])
            # Tentukan skala tampilan dengan margin
            if channel != "SpO2":
                y_range = max(abs(ch_min), abs(ch_max)) + y_margin
                plt.ylim(-y_range, y_range)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.suptitle(f"Lowest SpO2 Level {min_spo2}", fontsize=14)
        plt.savefig(save_path)
        plt.close()

        with open(save_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        return save_path, img_base64, None

    except Exception as e:
        return None, None, str(e)

def get_apnea(edf_file, start_time=60, end_time=360):
    try:
        raw = mne.io.read_raw_edf(edf_file, preload=True)
        
        sfreq = int(raw.info["sfreq"])
        spo2_data = raw.copy().pick_channels(["Flow"]).get_data()[0]

        start_idx = start_time * sfreq
        end_idx = end_time * sfreq

        time_value = []

        for start_time in range(60,end_time,1):
            time_value.append(spo2_data[start_time:start_time+1].tolist())

        segment = spo2_data[start_idx:end_idx]
        value = {
            "min":np.min(segment),
            "max":np.max(segment),
            "average":np.average(segment),
            "length":len(segment),
            "time_value":time_value
        }
    except Exception as e:
        return None, f"error:{e}"
    return value, None


def compute_amplitude(signal, distance):
    peaks, _ = find_peaks(signal, distance=distance)
    troughs, _ = find_peaks(-signal, distance=distance)

    peak_vals = signal[peaks]
    trough_vals = signal[troughs]

    num = min(len(peak_vals), len(trough_vals))
    amplitudes = np.abs(peak_vals[:num] - trough_vals[:num])

    return amplitudes, peaks[:num], troughs[:num]

def detect_apnea_by_amplitude(signal, drop_threshold=0.3, window_size=10):
    try:
        raw = mne.io.read_raw_edf(signal, preload=True)
        sfreq = raw.info['sfreq']
        distance = int(sfreq * 0.8)
        
        print("sebelum compute amplitude")
        flow_signal = raw.copy().pick_channels(['Flow']).get_data().flatten()
        amplitudes, peaks, troughs = compute_amplitude(flow_signal, distance)
        baseline_amp = np.mean(amplitudes[:int(len(amplitudes) * 0.1)])
        print("setelah compute amplitude")

        apnea_events = []
        window_len = int(window_size * sfreq / distance) 

        print("sebelum loop")
        for i in range(0, len(amplitudes) - window_len):
            window_amp = amplitudes[i:i + window_len]
            avg_amp = np.mean(window_amp)

            if avg_amp < (1 - drop_threshold) * baseline_amp:
                start_time = peaks[i] / sfreq
                end_time = peaks[i + window_len] / sfreq
                apnea_events.append((start_time, end_time))

        print("setelah loop")
        return apnea_events, None
    except Exception as e:
        return None, f"{e}"
