#detection_route.py

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
from app.utils.auth import token_required
from app.response import ModelResponse, BadRequest
from app.models import Deteksi, db
from sleep_apnea_model.model import preprocess_with_trim, predict, preprocess
from utils.extraction import find_s2_notation
import tempfile

detection_bp = Blueprint('detection_bp', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'edf', 'csv', 'txt'}
models = ["CNN", "LSTM"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@detection_bp.route('', methods=['POST'])
@token_required
def detect_sleep_apnea(current_user_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files.get("file")
    annotation = request.files.get("annotation")
    model_type = request.form.get("model")
    model_type = model_type.upper() if model_type else models[0]
    if file and allowed_file(file.filename):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".edf") as temp_file:
            file.save(temp_file.name)
            temp_filename = temp_file.name

        try:
            fft = model_type.upper() == models[1]
            model_path = f"app/sleep_apnea_model/model/{model_type.upper()}.h5"
            if model_type not in models:
                return jsonify(BadRequest(error="Model Does Not Exists"))
            
            annotated = annotation != None
            if annotated and annotation and allowed_file(annotation.filename):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_anno:
                        annotation.save(temp_anno.name)
                        annotation_filename = temp_anno.name
                try:
                    segments = find_s2_notation(annotation_filename)

                    apnea = 0 
                    total = 0
                    for start_time, end_time in segments:
                        processed_data, data = preprocess_with_trim(temp_filename, fft, start_time, end_time)
                        prediction = predict(processed_data, model_path)
                        if "apnea" in prediction:
                            apnea += 1
                            total += 1
                        else:
                            total += 1
                        os.remove(data)
                        
                    score = 0
                    if total and apnea != 0:
                        score = (apnea/total)*100
                    status = "Normal"
                    if score > 66:
                        status = "Apnea"
                    deteksi = Deteksi(user_id=current_user_id, apnea_status=status)
                    db.session.add(deteksi)
                    db.session.commit()
                    return jsonify(ModelResponse(200, "Prediction Success", f"{score:.2f}%").to_dict())
                finally:
                    try:
                        os.remove(annotation_filename)
                    except PermissionError as e:
                        print(f"Error Deleteing File: {e}")
            else:
                processed_data = preprocess(temp_filename, fft) 
                prediction = predict(processed_data, model_path)
                deteksi = Deteksi(user_id=current_user_id, apnea_status=prediction)
                db.session.add(deteksi)
                db.session.commit()

                return jsonify(ModelResponse(200, "Prediction Success", prediction).to_dict())
        finally:
            os.remove(temp_filename)
    else:
        return jsonify(BadRequest(error="File Not Supported").to_dict())

