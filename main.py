#!/usr/bin/env python3
from ast import Try
from http import client
import socket
import argparse
import os
import hashlib
import json
from sys import exception
from typing import final

version = "0.0.5"
phrase = {
    'exit': "EXIT",
}

def handshake_send(sock, ip, port, timeout=5):
    """
    Perform a handshake between sender and receiver.
    Returns True if the handshake is successful, False otherwise.
    """
    try:
        # Send a handshake message
        sock.sendto(b"handshake", (ip, port))
        # Wait for acknowledgment
        sock.settimeout(timeout)  # Timeout after 5 seconds
        data, _ = sock.recvfrom(1024)
        if data.decode() == "ack":
            return True
        return False
    except socket.timeout:
        print("Handshake failed: timeout")
        return False
    

def handshake_receive(sock):
    """
    Perform a handshake between sender and receiver.
    Returns True if the handshake is successful, False otherwise.
    """
    try:
        data, address = sock.recvfrom(1024)
        if data.decode() == "handshake":
            # Send acknowledgment
            sock.sendto(b"ack", address)
            return True
        return False
    except exception as e:
        print(f"Handshake failed: {e}")
        return False

def validate_hash(path, hash):
    if get_hash(path) == hash:
        return True
    else:
        return False

def get_hash(path):
    with open(path, 'rb') as f:
        data = f.read()
        return hashlib.md5(data).hexdigest()

def send_file_udp(ip, port, file_path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Sending {file_path} to {ip}:{port}")

    print(f"Performing handshake...")
    if not handshake_send(sock, ip, port, timeout=0.5):
        print("Ensure that the receiver is open and listening on the correct port.")
        return
    print(f"Handshake successful.")

    with open(file_path, 'rb') as f:
        # get file size and hash
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = get_hash(file_path)
        metadata = {
            'name': file_name,
            'size': file_size,
            'hash': file_hash
        }
        sock.sendto(json.dumps(metadata).encode(), (ip, port))
        while True:
            data = f.read(1024)
            if not data:
                break
            sock.sendto(data, (ip, port))
            # print progress
            print(f"Progress: {f.tell()}/{file_size}", end='\r')
    print(f"\ncomplete. [{file_path}]")


def send_file_tcp(ip, port, file_path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Sending {file_path} to {ip}:{port}")
    try:
        print("Connecting...")
        sock.connect((ip, port))

        # prepare metadata
        file_size = os.path.getsize(file_path)
        metadata = {
            'name': os.path.basename(file_path),
            'size': file_size,
            'hash': get_hash(file_path)
        }
        # send metadata
        sock.sendall(json.dumps(metadata).encode())

        # wait for acknowledgment
        ack = sock.recv(1024)
        if ack.decode() != "ACK":
            print("Failed to receive acknowledgment.")
            return
        
        # send file
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                sock.sendall(data)
                # print progress
                print(f"Progress: {f.tell()}/{file_size}", end='\r')
        print(f"\ncomplete. [{file_path}]") 
    except Exception as e:
        print(f"\nError in sending file: {e}")
    finally:
        sock.close()


def send_file(args):
    ip = args.ip
    port = args.port
    file_path = args.file_path
    if args.tcp: 
        send_file_tcp(ip, port, file_path)
    else:
        send_file_udp(ip, port, file_path)
    


def recieve_file_udp(port, save_dir):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', port))
    print(f"Listening for file on port {port}...")

    if not handshake_receive(sock):
        print("Handshake failed.")
        return
    
    # get metadata
    metadata, address = sock.recvfrom(1024)
    try:
        metadata = json.loads(metadata.decode())
    except Exception as e:
        print(f"Failed to decode metadata: {e}")
        print(f"metadata: {metadata}")
        return
    file_name = metadata['name']
    file_size = metadata['size']
    file_hash = metadata['hash']
    print(f"Receiving file from {address}...")

    file_path = os.path.join(save_dir, file_name)
    # create directory if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    try:
        with open(file_path, 'wb') as f:
            while True:
                data, address = sock.recvfrom(1024)
                if not data:
                    break
                f.write(data)
                # print progress
                print(f"Progress: {f.tell()}/{file_size}", end='\r')
                # set timeout to 3 seconds
                sock.settimeout(3)
                # check if file is complete
                if f.tell() == file_size:
                    print(f"\ncomplete. [{file_path}]")
                    break
    except socket.timeout:
        print(f"File transfer timed out.")
        return
    except Exception as e:
        print(f"File transfer failed: {e}")
        return
    print(f"Validating file...")
    try:
        if validate_hash(file_path, file_hash):
            print(f"File validated.")
        else:
            print(f"File validation failed! Expected {file_hash} but got {get_hash(file_path)}.")
    except Exception as e:
        print(f"File validation failed! {e}")

def recieve_files_udp(port, save_dir):
        while True:
            recieve_file_udp(port, save_dir)

def recieve_file_tcp(port, save_dir):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('0.0.0.0', port))
    server_sock.listen(1)
    print(f"Listening for file on port {port}...")

    client_sock, address = server_sock.accept()
    print(f"Receiving file from {address}...")

    # get metadata
    metadata = client_sock.recv(1024).decode()
    try:
        metadata = json.loads(metadata)
        file_name = metadata['name']
        file_size = metadata['size']
        file_hash = metadata['hash']

        client_sock.sendall(b"ACK")
    except Exception as e:
        print(f"Failed to decode metadata: {e}")
        print(f"metadata: {metadata}")
        server_sock.close()
        client_sock.close()
        return
     
    # receive file
    try:
        # create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, file_name), 'wb') as f:
            while True:
                data = client_sock.recv(1024)
                if not data:
                    break
                f.write(data)
                # print progress
                print(f"Progress: {f.tell()}/{file_size}", end='\r')
                # check if file is complete
                if f.tell() == file_size:
                    print(f"\ncomplete. [{file_name}]")
                    break
        print(f"Validating file...")
        if validate_hash(os.path.join(save_dir, file_name), file_hash):
            print(f"File validated.")
        else:
            print(f"File validation failed! Expected {file_hash} but got {get_hash(os.path.join(save_dir, file_name))}.")
    except Exception as e:
        print(f"File transfer failed: {e}")
        return
    finally:
        client_sock.close()
        server_sock.close()

def recieve_files_tcp(port, save_dir):
    while True:
        recieve_file_tcp(port, save_dir)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def receive_messages(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', args.port))
    print(f"Listening for messages on port {args.port}...")

    while True:
        message, address = sock.recvfrom(1024)
        if message.decode() == phrase['exit']:
            break
        if args.annomyous:
            print(f"{message.decode()}")
        else:
            print(f"Message from {address}: {message.decode()}")

def send_messages(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Sending messages to {args.ip}:{args.port}")

    while True:
        message = input("send: ")
        sock.sendto(message.encode(), (args.ip, args.port))
        if message == phrase['exit']:
            break

def recieve_file(args):
    port = args.port
    file_dir = args.file_dir
    if args.tcp:
        if args.recursive:
            recieve_files_tcp(port, file_dir)
        else:
            recieve_file_tcp(port, file_dir)
    else:
        if args.recursive:
            recieve_files_udp(port, file_dir)
        else:
            recieve_file_udp(port, file_dir)


def main():
    parser = argparse.ArgumentParser(description=f"UDP Chat Application v{version}")
    parser.add_argument('-v', '--version', action='store_true', help='Print version')
    parser.add_argument('-i', '--get-ip', action='store_true', help='Print local IP address')
    subparsers = parser.add_subparsers(dest='command')

    # Post command parser
    post_parser = subparsers.add_parser('post')
    post_subparsers = post_parser.add_subparsers(dest='type')

    # Post message
    post_msg_parser = post_subparsers.add_parser('msg')
    post_msg_parser.add_argument('ip', type=str, help='Target IP address')
    post_msg_parser.add_argument('port', type=int, help='Port number')
    post_msg_parser.set_defaults(func=send_messages)

    # Post file
    post_file_parser = post_subparsers.add_parser('file')
    post_file_parser.add_argument('ip', type=str, help='Target IP address')
    post_file_parser.add_argument('port', type=int, help='Port number')
    post_file_parser.add_argument('file_path', type=str, help='File path to send')
    post_file_parser.add_argument('--tcp', action='store_true', help='Use TCP instead of UDP. More reliable but slower.')
    post_file_parser.set_defaults(func=send_file)

    # Get command parser
    get_parser = subparsers.add_parser('get')
    get_subparsers = get_parser.add_subparsers(dest='type')

    # Get message
    get_msg_parser = get_subparsers.add_parser('msg')
    get_msg_parser.add_argument('port', type=int, help='Port number')
    get_msg_parser.add_argument('-a', '--annomyous', action='store_true', help='Receive messages annomyously')
    get_msg_parser.set_defaults(func=receive_messages)

    # Get file
    get_file_parser = get_subparsers.add_parser('file')
    get_file_parser.add_argument('port', type=int, help='Port number')
    get_file_parser.add_argument('file_dir', type=str, help='File directory to save to')
    get_file_parser.add_argument('-r', '--recursive', action='store_true', help='Receive files recursively')
    get_file_parser.add_argument('--tcp', action='store_true', help='Use TCP instead of UDP. More reliable but slower.')
    get_file_parser.set_defaults(func=recieve_file)

    args = parser.parse_args()

    if args.version:
        print(f"{version}")
    elif args.get_ip:
        print(f"{get_local_ip()}")
    elif hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()