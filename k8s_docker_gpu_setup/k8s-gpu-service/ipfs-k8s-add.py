import requests

def upload_file_to_ipfs(file_path, api_base_url='http://127.0.0.1:5001'):
    """
    Uploads a file to IPFS and returns the hash of the uploaded file.
    
    :param file_path: Path to the file you want to upload.
    :param api_base_url: The base URL for your IPFS HTTP API (default is localhost).
    :return: CID or hash of the uploaded file.
    """
    # Prepare the file for uploading
    with open(file_path, 'rb') as f:
        files = {'file': f}
        
        # Send the POST request to add the file to IPFS
        response = requests.post(f'{api_base_url}/api/v0/add', files=files)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response to get the hash
            result = response.json()
            return result['Hash']
        else:
            print(f"Failed to upload file: {response.text}")
            return None

# Example usage
if __name__ == "__main__":
    file_path = '/tmp/file.txt'  # Replace with your file path
    file_hash = upload_file_to_ipfs(file_path,api_base_url='http://127.0.0.1:30051')
    if file_hash:
        print(f"File uploaded successfully! You can access it via: https://ipfs.io/ipfs/{file_hash}")
