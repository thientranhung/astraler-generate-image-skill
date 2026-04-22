#!/usr/bin/env python3
import urllib.request
import urllib.parse
import json
import base64
import os
import sys
import argparse

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")

def generate_image(prompt, output_file, model_name=None, aspect_ratio="1:1"):
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set. Please configure it in the .env file.", file=sys.stderr)
        sys.exit(1)

    if not model_name:
        model_name = os.environ.get("IMAGE_MODEL", "gemini-3-pro-image-preview")

    encoded_model = urllib.parse.quote(model_name)
    is_gemini_model = model_name.startswith("gemini")
    
    if is_gemini_model:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:generateContent?key={api_key}"
        # For Gemini 3 image models, we inject aspect ratio into generationConfig or prompt
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt + f" (Aspect ratio: {aspect_ratio})"}
                    ]
                }
            ]
        }
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:predict?key={api_key}"
        payload = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "outputOptions": {
                    "mimeType": "image/png"
                }
            }
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            b64_image = None
            if is_gemini_model:
                candidates = result.get("candidates", [])
                if not candidates:
                    print("Error: No candidates returned.", file=sys.stderr)
                    print(json.dumps(result, indent=2), file=sys.stderr)
                    sys.exit(1)
                
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "inlineData" not in parts[0]:
                    print("Error: No inlineData returned in the response.", file=sys.stderr)
                    print(json.dumps(result, indent=2), file=sys.stderr)
                    sys.exit(1)
                    
                b64_image = parts[0]["inlineData"].get("data")
            else:
                predictions = result.get("predictions", [])
                if not predictions:
                    print("Error: No predictions returned.", file=sys.stderr)
                    print(json.dumps(result, indent=2), file=sys.stderr)
                    sys.exit(1)
                    
                b64_image = predictions[0].get("bytesBase64Encoded") or predictions[0].get("bytesBase64")
            
            if not b64_image:
                print("Error: No image bytes returned.", file=sys.stderr)
                sys.exit(1)
                
            image_data = base64.b64decode(b64_image)
            with open(output_file, "wb") as f:
                f.write(image_data)
            print(f"Image successfully generated and saved to {output_file}")
            
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate images using Google Gemini/Imagen API")
    parser.add_argument("--prompt", required=True, help="Text prompt for the image")
    parser.add_argument("--output", required=True, help="Output file path (e.g. output.png)")
    parser.add_argument("--model", help="Model name (overrides .env)")
    parser.add_argument("--aspect_ratio", default="1:1", help="Aspect ratio, e.g. 1:1, 16:9, 9:16, 4:3, 3:4")
    
    args = parser.parse_args()
    
    generate_image(args.prompt, args.output, args.model, args.aspect_ratio)
