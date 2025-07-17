#detection_route.py

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
from app.utils.auth import token_required
from app.response import ModelResponse, BadRequest, ResultResponse, FixedModelResponse
from app.models import Deteksi, db
from sleep_apnea_model.model import preprocess_with_trim, predict, preprocess, convert_csv_to_edf_selected_channels, detect_apnea_by_amplitude
from sleep_apnea_model.model import find_non_annotatated_segments, duration_check, check_oxygen_desaturation, visualize_segment, load_signal, channels_check
from utils.extraction import find_s2_notation
import tempfile
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)

detection_bp = Blueprint('detection_bp', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'edf', 'txt', 'csv'}
models = ["CNN", "LSTM"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_exts):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts

@detection_bp.route('/rule_based_detect', methods=['POST'])
def rule_based_detect():
    if 'file' not in request.files:
        return jsonify({"error":"no files selected"})
    file = request.files.get('file')
    with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as temp_file:
        file.save(temp_file.name)
        filename = temp_file.name
    try:
        print("masuk api")
        # result, err = get_apnea(filename)
        apnea_lists, err = detect_apnea_by_amplitude(filename, window_size=20)
        if err is not None:
            print(f"{err}")
            return jsonify({"error":f"{err}"})
        return jsonify({
            "message":"success",
            "code":200,
            "result":{
                "apnea_count":len(apnea_lists),
                "apnea_lists":apnea_lists
            }
        })
    except Exception as e:
        return jsonify({"error":f"{e}"})
    
@detection_bp.route('/apnea_csv', methods=['POST'])
# @token_required()
def detect_sleep_apnea_csv():
    if 'file' not in request.files:
        return jsonify({"error":"No file part in request"}), 400
    file = request.files.get('file')
    model_type = request.form.get('modelType')
    if model_type is None:
        return jsonify({"error": "model cannot be empty"})
    if allowed_file(file.filename, {'csv'}):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name
        try:
            converted_file, err = convert_csv_to_edf_selected_channels(temp_filename, 8)
            if err is not None:
                return jsonify({"error":f"{err}"}), 500
            _, err = duration_check(converted_file)
            if err is not None:
                return jsonify({"error":err}), 400
            fft = model_type.lower() == models[1].lower()
            start_time = 0
            apnea_counts = 0
            total = 0
            min_spo2 = 100
            min_spo2_start_time = 0
            # min_oxygen_list = []
            is_normal = True
            for start_time in range(0,3600,10):
                end_time = start_time + 11
                if model_type == "CNN":
                    end_time = start_time + 10
                processed_signal, signal_data = preprocess_with_trim(converted_file, fft, start_time, end_time)
                prediction = predict(processed_signal, model_type)
                if prediction == "apnea":
                    apnea_counts += 1
                total += 1
                #check oxygen desaturation
                min_oxygen_level = check_oxygen_desaturation(converted_file, start_time)
                min_oxygen_level = min_oxygen_level * 1000015
                print(f"min oxygen: {min_oxygen_level}")
                if min_oxygen_level < min_spo2 :
                    if min_oxygen_level < 90 and prediction == "apnea":
                        min_spo2 = min_oxygen_level
                        min_spo2_start_time = start_time
                        is_normal = False
                    else:
                        min_spo2 = min_oxygen_level
                        min_spo2_start_time = start_time
                # min_oxygen_list.append(min_oxygen_level)
                os.remove(signal_data)
            min_spo2 = round(min_spo2, 2)
            # print(f"oxygen level list: {min_oxygen_list}")
            visual_path, base64 = visualize_segment(converted_file, 5, int(min_spo2_start_time), min_spo2)
            normal_counts = total - apnea_counts
            result = ResultResponse(
                apnea_count=apnea_counts,
                normal_count=normal_counts,
                lowest_spo2=min_spo2,
                lowest_spo2_visual=base64
            )
            response = FixedModelResponse(
                code=200,
                message="success",
                result=result
            )
            status = "normal" if is_normal else "apnea"
            # if apnea_counts > 0:
            #     status = "apnea" 
            # deteksi = Deteksi(user_id=current_user_id, apnea_status=status, visual=visual_path)
            # db.session.add(deteksi)                
            # db.session.commit()
            os.remove(converted_file)
            return jsonify(response.to_dict())
            
        except Exception as e:
            print("exception: {e}")
            return(jsonify({"error":f"{e}"}))
    else:
        return jsonify(BadRequest(error="File Not Supported").to_dict())

@detection_bp.route('/apnea_edf', methods=['POST'])
# @token_required
def detect_sleep_apnea_edf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400
    file = request.files.get('file')
    model_type = request.form.get("modelType")
    if model_type is None:
        return jsonify({"error":"Model cannot be empty"})
    if allowed_file(file.filename, {'edf'}):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name
        try:
            _, err = duration_check(temp_filename)
            if err is not None:
                return jsonify({"error":err}), 400
            fft = model_type.lower() == models[1].lower()
            cnn = model_type.lower() == models[0].lower()
            start_time = 0
            apnea_counts = 0
            total = 0
            min_spo2 = 100
            min_spo2_start_time = 0
            is_normal = True
            raw, resampled, err = load_signal(temp_filename, cnn)
            if err is not None:
                return jsonify({"error":f"{err}"})
            used_channels, err = channels_check(resampled)
            if err is not None:
                return jsonify({"error":f"{err}"})
            for start_time in range(3600,10800,30):
                end_time = start_time + 31
                if model_type == "CNN":
                    end_time = start_time + 30
                processed_signal, signal_data = preprocess_with_trim(resampled, fft, start_time, end_time, used_channels)
                prediction = predict(processed_signal, model_type)
                if prediction == "apnea":
                    apnea_counts += 1
                total += 1
                #check oxygen desaturation
                min_oxygen_level = check_oxygen_desaturation(raw, start_time)
                if min_oxygen_level < min_spo2 and min_oxygen_level > 50:
                    min_spo2 = min_oxygen_level
                    min_spo2_start_time = start_time
                    if min_oxygen_level < 90 and prediction == "apnea":
                        is_normal = False
                os.remove(signal_data)
            min_spo2 = round(min_spo2, 2)
            visual_path, base64, err = visualize_segment(raw, 5, int(min_spo2_start_time), min_spo2, used_channels)
            if err is not None:
                return jsonify({"error":f"{err}"})
            normal_counts = total - apnea_counts
            result = ResultResponse(
                apnea_count=apnea_counts,
                lowest_spo2=min_spo2,
                lowest_spo2_visual=base64
            )
            response = FixedModelResponse(
                code=200,
                message="success",
                result=result
            )
            status = "normal" if is_normal else "apnea"
            apnea_counts = 0 if is_normal else apnea_counts
            print(f"total:{total}")
            # status = "normal"
            # if apnea_counts > 0:
            #     status = "apnea" 
            # deteksi = Deteksi(user_id=current_user_id, apnea_status=status, visual=visual_path)
            # db.session.add(deteksi)                
            # db.session.commit()
            return jsonify(response.to_dict())
        except Exception as e:
            print(f"exception {e}")
            return jsonify({"code":500, "message":f"{e}"})    
    else:
        return jsonify(BadRequest(error="File Not Supported").to_dict())

@detection_bp.route('/csv', methods=['POST'])
@token_required
def detect_apnea_csv(current_user_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400
    file = request.files.get("file")
    model_type = request.form.get("model")
    duration = request.form.get("duration")
    if allowed_file(file.filename, {'csv'}):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name
        try:
            converted_file, err = convert_csv_to_edf_selected_channels(temp_filename)
            if err:
                return jsonify({"error": err}), 400
        except Exception as e:
            print(f"error: {e}")
            return jsonify({"error":f"error while converting file to .edf"}), 500
        try:
            fft = model_type.upper() == models[1]
            # model_path = f"app/sleep_apnea_model/model/{model_type.upper()}.h5"
            if model_type not in models:
                return jsonify(BadRequest(error="Model Does Not Exists"))
            if duration and duration is "6":
                processed_data = preprocess(converted_file, fft, model_type)
                prediction = predict(processed_data, model_type)
                return jsonify(ModelResponse(200, "Prediction Success", prediction))
            # total = 0
            # apnea = 0
            # for start_time in range (0, 10, 1):
            #     processed_data, signal_data = preprocess_with_trim(converted_file, fft, start_time, start_time+5) 
            #     prediction = predict(processed_data, model_path)
            #     if "apnea" in prediction:
            #         apnea += 1     
            #     total += 1
            #     os.remove(signal_data)        
            # score = 0
            # if total and apnea != 0:
            #     score = (apnea/total)*100
            # status = "Normal"
            # if score > 66:                        
            #     status = "Apnea"
            # print(f"status: {status}")
            start_time, err = find_non_annotatated_segments(converted_file)
            if err is not None:
                return jsonify(BadRequest(error=err))
            apnea_windows = []
            total = 0
            apnea_count = 0

            for start_time in range(0, 10, 1):
                processed_data, signal_data = preprocess_with_trim(converted_file, fft, start_time, start_time + 6, model_type)
                prediction = predict(processed_data, model_type)

                if "apnea" in prediction:
                    apnea_windows.append((start_time, start_time + 6))
                    apnea_count += 1

                total += 1
                os.remove(signal_data)
            accuracy = (apnea_count / total) * 100 if total > 0 else 0
            merged = []
            for start, end in sorted(apnea_windows):
                if not merged or merged[-1][1] < start:
                    merged.append([start, end])
                else:
                    merged[-1][1] = max(merged[-1][1], end)
            status = "Normal"
            for start, end in merged:
                if end - start >= 10:
                    status = "Apnea"
                    break
            deteksi = Deteksi(user_id=current_user_id, apnea_status=status)
            db.session.add(deteksi)                
            db.session.commit()
            return jsonify(ModelResponse(200, "Prediction Success", f"{accuracy:.2f}% Apnea Ratio").to_dict())
        finally:
            os.remove(temp_filename)
            os.remove(converted_file)
    else:
        return jsonify(BadRequest(error="File Not Supported").to_dict())

@detection_bp.route('/edf', methods=['POST'])
@token_required
def detect_sleep_apnea(current_user_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files.get("file")
    annotation = request.files.get("annotation")
    duration = request.form.get("duration")
    model_type = request.form.get("model")
    model_type = model_type.upper() if model_type else models[0]
    if allowed_file(file.filename, {'edf'}):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name

        try:
            fft = model_type.upper() == models[1]
            # model_path = f"app/sleep_apnea_model/model/{model_type.upper()}.h5"
            if model_type not in models:
                return jsonify(BadRequest(error="Model Does Not Exists"))
            
            annotated = annotation != None
            if annotated and annotation and allowed_file(annotation.filename, {"txt"}):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_anno:
                        annotation.save(temp_anno.name)
                        annotation_filename = temp_anno.name
                try:
                    segments = find_s2_notation(annotation_filename)

                    apnea_windows = []
                    apnea = 0 
                    total = 0
                    for start_time, end_time in segments:
                        processed_data, data = preprocess_with_trim(temp_filename, fft, start_time, end_time)
                        prediction = predict(processed_data, model_type)
                        if "apnea" in prediction:
                            apnea_windows.append((start_time, end_time))
                            apnea += 1
                        total += 1
                        os.remove(data)
                    accuracy = (apnea / total) * 100 if total > 0 else 0
                    merged = []
                    for start, end in sorted(apnea_windows):
                        if not merged or merged[-1][1] < start:
                            merged.append([start, end])
                        else:
                            merged[-1][1] = max(merged[-1][1], end)
                    status = "Normal"
                    for start, end in merged:
                        if end - start >= 10:
                            status = "Apnea"
                            break
                    deteksi = Deteksi(user_id=current_user_id, apnea_status=status)
                    db.session.add(deteksi)
                    db.session.commit()
                    return jsonify(ModelResponse(200, "Prediction Success", f"{accuracy:.2f}% Apnea Ratio").to_dict())
                finally:
                    try:
                        os.remove(annotation_filename)
                    except PermissionError as e:
                        print(f"Error Deleteing File: {e}")
            else:
                if duration and duration is "6":
                    processed_data = preprocess(temp_filename, fft) 
                    prediction = predict(processed_data, model_type)
                    deteksi = Deteksi(user_id=current_user_id, apnea_status=prediction)
                    db.session.add(deteksi)
                    db.session.commit()
                    return jsonify(ModelResponse(200, "Prediction Success", prediction).to_dict())
                else:
                    start_time, err = find_non_annotatated_segments(temp_filename)
                    if err is not None:
                        return jsonify(BadRequest(error=err))
                    apnea_windows = []
                    total = 0
                    apnea_count = 0
                    for start_time in range(0, 10, 1):
                        processed_data, signal_data = preprocess_with_trim(temp_filename, fft, start_time, start_time + 5)
                        prediction = predict(processed_data, model_type)
                        if "apnea" in prediction:
                            apnea_windows.append((start_time, start_time + 5))
                            apnea_count += 1
                        total += 1
                        os.remove(signal_data)
                    accuracy = (apnea_count / total) * 100 if total > 0 else 0
                    merged = []
                    for start, end in sorted(apnea_windows):
                        if not merged or merged[-1][1] < start:
                            merged.append([start, end])
                        else:
                            merged[-1][1] = max(merged[-1][1], end)
                    status = "Normal"
                    for start, end in merged:
                        if end - start >= 10:
                            status = "Apnea"
                            break
                    deteksi = Deteksi(user_id=current_user_id, apnea_status=status)
                    db.session.add(deteksi)                
                    db.session.commit()
                    return jsonify(ModelResponse(200, "Prediction Success", f"{accuracy:.2f}% Apnea Ratio").to_dict())
        finally:
            os.remove(temp_filename)
    else:
        return jsonify(BadRequest(error="File Not Supported").to_dict())