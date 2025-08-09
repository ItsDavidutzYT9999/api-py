# IPA Processing API

A Python Flask API for processing iOS App Package (IPA) files and generating itms-services URLs for over-the-air app installation.

## Features

- Upload IPA files via REST API
- Extract app metadata (bundle ID, name, version)
- Generate manifest.plist files automatically
- Create itms-services URLs for iOS installation
- CORS enabled for Swift app integration

## Installation

1. Install dependencies:
```bash
pip install flask flask-cors gunicorn werkzeug
```

2. Run the server:
```bash
# Development
python app.py

# Production
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## API Endpoints

### POST /api/upload
Upload an IPA file and get installation URLs.

**Request:**
- Content-Type: multipart/form-data
- Field: `file` (IPA file)

**Response:**
```json
{
  "success": true,
  "metadata": {
    "bundle_id": "com.example.app",
    "app_name": "Example App",
    "version": "1.0",
    "build_version": "1"
  },
  "itms_url": "itms-services://?action=download-manifest&url=...",
  "manifest_url": "https://...",
  "ipa_url": "https://...",
  "id": "unique-id"
}
```

### GET /api/status
Check API health status.

### GET /
API information and available endpoints.

## Directory Structure

```
your-project/
├── app.py           # Main application
├── main.py          # Entry point for gunicorn
├── static/
│   ├── uploads/     # Uploaded IPA files
│   └── manifests/   # Generated manifest files
```

## Usage in Swift

```swift
// Upload IPA file
let url = URL(string: "http://your-api.com/api/upload")!
var request = URLRequest(url: url)
request.httpMethod = "POST"

let formData = MultipartFormData()
formData.append(ipaData, withName: "file", fileName: "app.ipa", mimeType: "application/octet-stream")

request.setValue("multipart/form-data; boundary=\(formData.boundary)", forHTTPHeaderField: "Content-Type")
request.httpBody = formData.httpBody

// Handle response with itms_url for installation
```

## Security Notes

- Only accepts .ipa files
- 500MB file size limit
- Secure filename handling
- Environment-based configuration

## License

Open source - use as needed for your projects.