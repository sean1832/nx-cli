import socket
import json
import os
import sys

from . import utilities as utils

def send_file_tcp(ip, port, file_path, chunk, verbose=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if verbose: print("TCP Socket created.")
    if verbose: print(f"Sending {file_path} to {ip}:{port}")
    try:
        msg = "Connecting..."
        print(msg, end='\r')
        sys.stdout.flush() # Ensure "Connecting..." is printed immediately
        sock.connect((ip, port))
        print("Connected.".ljust(len(msg)))

        # prepare metadata
        file_size = os.path.getsize(file_path)
        metadata = {
            'name': os.path.basename(file_path),
            'size': file_size,
            'hash': utils.get_hash(file_path)
        }
        # send metadata
        msg = "Sending metadata..."
        if verbose: print(msg, end='\r')
        sock.sendall(json.dumps(metadata).encode())
        if verbose: print("Metadata sent.".ljust(len(msg)))

        # wait for acknowledgment
        msg = "Waiting for acknowledgment..."
        if verbose: print(msg, end='\r')
        ack = sock.recv(1024)
        if ack.decode() != "ACK":
            print("Failed to receive acknowledgment.")
            return
        if verbose: print("Acknowledgment received.".ljust(len(msg)))
        
        # send file
        if verbose: print("Sending file...")
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk)
                if not data:
                    break
                sock.sendall(data)

                # print progress
                utils.print_progress(f.tell(), file_size, verbose, unit='kb')
        print(f"\ncomplete. [{file_path}]") 
    except socket.error as e:
        print(f"\nError in sending file: {e}")
    finally:
        sock.close()
        if verbose: print("TCP Socket closed.")

def recieve_file_tcp(port, save_dir, chunk, verbose=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if verbose: print("TCP server socket created.")
    server_sock.bind(('0.0.0.0', port))
    server_sock.listen(1)
    print(f"Listening for file on port {port}...")

    client_sock, address = server_sock.accept()
    if verbose: print(f"Connection established with {address}.")
    if verbose: print('TCP client socket created.')

    # get metadata
    msg = "Waiting for metadata..."
    if verbose: print(msg, end='\r')
    metadata = client_sock.recv(1024).decode()
    if verbose: print("Metadata received.".ljust(len(msg)))

    try:
        msg = "decoding metadata..."
        if verbose: print(msg, end='\r')
        metadata = json.loads(metadata)
        file_name = metadata['name']
        file_size = metadata['size']
        file_hash = metadata['hash']
        if verbose: print("Metadata decoded.".ljust(len(msg)))

        # send acknowledgment
        msg = "Sending acknowledgment..."
        if verbose: print(msg, end='\r')
        client_sock.sendall(b"ACK")
        if verbose: print("Acknowledgment sent.".ljust(len(msg)))
    except Exception as e:
        print(f"Failed to decode metadata: {e}")
        print(f"metadata: {metadata}")
        server_sock.close()
        client_sock.close()
        print("TCP Socket closed.")
        return
     
    # receive file
    try:
        # create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, file_name), 'wb') as f:
            if verbose: print(f"Receiving file from {address}...")
            while True:
                data = client_sock.recv(chunk)
                if not data:
                    break
                f.write(data)

                # print progress
                utils.print_progress(f.tell(), file_size, verbose, unit='kb')

                # check if file is complete
                if f.tell() == file_size:
                    print(f"\ncomplete. [{file_name}]")
                    break
        msg = 'Validating file...'
        print(msg, end='\r')
        if utils.validate_hash(os.path.join(save_dir, file_name), file_hash):
            print(f"File validated.".ljust(len(msg)))
        else:
            print(f"File validation failed! Expected {file_hash} but got {utils.get_hash(os.path.join(save_dir, file_name))}.")
    except socket.error as e:
        print(f"File transfer failed: {e}")
        return
    finally:
        client_sock.close()
        if verbose: print("TCP client socket closed.")
        server_sock.close()
        if verbose: print("TCP server socket closed.")

def recieve_files_tcp(port, save_dir, chunk, verbose=False):
    try:
        while True:
            recieve_file_tcp(port, save_dir, chunk, verbose=verbose)
    except KeyboardInterrupt:
        print("Manual Exit.")
        return