
import mne
import numpy as np
import tensorflow as tf
from scipy.fft import fft

channel_names = ["TERMISTORE", "TORACE", "ADDOME", "SpO2"]
class_labels = ["apnea", "normal"]

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

def trim_signal(signal, start_time, end_time):
    raw = mne.io.read_raw_edf(signal, preload=True)
    fs = int(raw.info['sfreq'])

    trimmed_signals = {}
    raw.crop(tmin=start_time, tmax=end_time)

    for ch in channel_names:
        if ch in raw.ch_names:
            data = raw.copy().pick([ch])
            if ch == "SpO2":
                data = data.get_data()[0]
                data = np.clip(data, 0, 200)
                data = (data - np.min(data)) / (np.max(data) - np.min(data)) * 100
                data = np.round(data).astype(np.int16)

                info = mne.create_info([ch], sfreq=fs, ch_types="misc")
                data = mne.io.RawArray(data.reshape(1, -1), info)

            trimmed_signals[ch] = data.get_data()[0]
        else:
            print(f"Channel {ch} not found in EDF file.")

    return trimmed_signals, fs

def combine_signal(stacked_signal, fs, start_time, end_time):
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

def preprocess_with_trim(raw_signal, fft, start_time=1000, end_time=1005):
    stacked_signal, fs = trim_signal(raw_signal, start_time, end_time)
    signal_data = combine_signal(stacked_signal, fs, start_time, end_time)

    processed_signal = signal_data
    processed_signal = mne.io.read_raw_edf(processed_signal, preload=True)
    processed_signal = processed_signal.get_data()

    processed_signal = np.nan_to_num(processed_signal, nan=0.0, posinf=1.0, neginf=-1.0)

    min_val = np.min(processed_signal, axis=1, keepdims=True)
    max_val = np.max(processed_signal, axis=1, keepdims=True)
    processed_signal = (processed_signal - min_val) / (max_val - min_val + 1e-8)

    processed_signal = processed_signal.T
    processed_signal = np.expand_dims(processed_signal, axis=0)

    processed_signal = np.array(processed_signal, dtype=np.float32)
    if fft:
        processed_signal = toFFT(processed_signal)

    processed_signal = reshape_signals(processed_signal)

    return processed_signal, signal_data

def reshape_signals(X):
    return X.reshape((X.shape[0], X.shape[1], X.shape[2]))

def preprocess(file, fft):
    signal_data = mne.io.read_raw_edf(file, preload=True)
    signal_data = signal_data.get_data()

    signal_data = np.nan_to_num(signal_data, nan=0.0, posinf=1.0, neginf=-1.0)

    min_val = np.min(signal_data, axis=1, keepdims=True)
    max_val = np.max(signal_data, axis=1, keepdims=True)
    signal_data = (signal_data - min_val) / (max_val - min_val + 1e-8)

    signal_data = signal_data.T
    signal_data = np.expand_dims(signal_data, axis=0)

    signal_data = np.array(signal_data, dtype=np.float32)
    signal_data = reshape_signals(signal_data)
    if fft:
        signal_data = toFFT(signal_data)


    return signal_data

def predict(processed_signal, model_path):
    model = tf.keras.models.load_model(model_path)
    prediction = model.predict(processed_signal)
    if prediction.shape[-1] == 1:
        predicted_class = int(prediction[0][0] >= 0.5)
    else:
        predicted_class = np.argmax(prediction)
    print(f"Predicted Class: {class_labels[predicted_class]}\n")

    return class_labels[predicted_class]