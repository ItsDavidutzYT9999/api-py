import os
import logging
import zipfile
import plistlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Enable CORS for Swift app requests
CORS(app)

# Configuration
UPLOAD_FOLDER = 'static/uploads'
MANIFEST_FOLDER = 'static/manifests'
ALLOWED_EXTENSIONS = {'ipa'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MANIFEST_FOLDER'] = MANIFEST_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MANIFEST_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_ipa_metadata(ipa_path):
    """Extract metadata from IPA file"""
    try:
        with zipfile.ZipFile(ipa_path, 'r') as zip_file:
            # Find Info.plist in the app bundle
            info_plist_path = None
            for file_info in zip_file.filelist:
                if file_info.filename.endswith('.app/Info.plist'):
                    info_plist_path = file_info.filename
                    break
            
            if not info_plist_path:
                raise ValueError("Info.plist not found in IPA file")
            
            # Extract and parse Info.plist
            with zip_file.open(info_plist_path) as plist_file:
                plist_data = plistlib.load(plist_file)
                
                bundle_id = plist_data.get('CFBundleIdentifier')
                app_name = plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName')
                version = plist_data.get('CFBundleShortVersionString', '1.0')
                build_version = plist_data.get('CFBundleVersion', '1')
                
                if not bundle_id or not app_name:
                    raise ValueError("Required metadata not found in Info.plist")
                
                return {
                    'bundle_id': bundle_id,
                    'app_name': app_name,
                    'version': version,
                    'build_version': build_version
                }
                
    except Exception as e:
        logging.error(f"Error extracting IPA metadata: {str(e)}")
        raise ValueError(f"Invalid IPA file: {str(e)}")

def generate_manifest_plist(metadata, ipa_url):
    """Generate manifest.plist content for iOS installation"""
    manifest = {
        'items': [
            {
                'assets': [
                    {
                        'kind': 'software-package',
                        'url': ipa_url
                    }
                ],
                'metadata': {
                    'bundle-identifier': metadata['bundle_id'],
                    'bundle-version': metadata['version'],
                    'kind': 'software',
                    'title': metadata['app_name']
                }
            }
        ]
    }
    return manifest

@app.route('/')
def index():
    """API root endpoint"""
    return jsonify({
        'name': 'IPA Processing API',
        'version': '1.0',
        'description': 'API for processing IPA files and generating itms-services URLs',
        'endpoints': {
            'upload': '/api/upload',
            'status': '/api/status'
        }
    })

@app.route('/api/upload', methods=['POST'])
def upload_ipa():
    """Handle IPA file upload and processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only .ipa files are allowed'}), 400
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        filename = f"{unique_id}.ipa"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save uploaded file
        file.save(filepath)
        logging.info(f"Saved IPA file: {filepath}")
        
        # Extract metadata
        try:
            metadata = extract_ipa_metadata(filepath)
            logging.info(f"Extracted metadata: {metadata}")
        except Exception as e:
            # Clean up uploaded file if metadata extraction fails
            os.remove(filepath)
            return jsonify({'error': str(e)}), 400
        
        # Generate URLs (use HTTPS for production)
        scheme = 'https' if request.is_secure else 'http'
        base_url = f"{scheme}://{request.host}"
        
        ipa_url = f"{base_url}/static/uploads/{filename}"
        
        # Generate manifest.plist
        manifest_data = generate_manifest_plist(metadata, ipa_url)
        manifest_filename = f"{unique_id}.plist"
        manifest_path = os.path.join(app.config['MANIFEST_FOLDER'], manifest_filename)
        
        with open(manifest_path, 'wb') as manifest_file:
            plistlib.dump(manifest_data, manifest_file)
        
        manifest_url = f"{base_url}/static/manifests/{manifest_filename}"
        
        # Generate itms-services URL
        itms_url = f"itms-services://?action=download-manifest&url={manifest_url}"
        
        response_data = {
            'success': True,
            'metadata': metadata,
            'itms_url': itms_url,
            'manifest_url': manifest_url,
            'ipa_url': ipa_url,
            'id': unique_id
        }
        
        logging.info(f"Generated response: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded IPA files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, 
                             mimetype='application/octet-stream')

@app.route('/static/manifests/<filename>')
def manifest_file(filename):
    """Serve manifest.plist files"""
    return send_from_directory(app.config['MANIFEST_FOLDER'], filename, 
                             mimetype='application/xml')

@app.route('/api/status')
def status():
    """API status endpoint"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    })

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 500MB'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
