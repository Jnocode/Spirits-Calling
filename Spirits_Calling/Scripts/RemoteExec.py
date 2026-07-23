import socket
import sys
import os
import json
import time
import uuid

def remote_exec_magic(file_path):
    # Standard Unreal Multicast Group
    MCAST_GRP = '239.0.0.1'
    MCAST_PORT = 6766
    
    # 1. UDP Discovery with MAGIC
    print(f"Scanning for Unreal Editor via Multicast {MCAST_GRP}:{MCAST_PORT} (Magic: ue_py)...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(3)
    
    # Set TTL
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    
    # Ping Message (Now with MAGIC)
    ping_data = {
        "magic": "ue_py",        # <--- VITAL
        "version": 1,
        "type": "ping",          # Type ping (not command)
        "source": str(uuid.uuid4())
    }
    
    tcp_host = None
    tcp_port = None
    
    try:
        sock.sendto(json.dumps(ping_data).encode('utf-8'), (MCAST_GRP, MCAST_PORT))
        
        # 2. Wait for Response
        start_time = time.time()
        while time.time() - start_time < 3:
            try:
                data, addr = sock.recvfrom(4096)
                resp = json.loads(data.decode('utf-8'))
                
                # Check magic response
                if resp.get('magic') != 'ue_py':
                    continue
                    
                if resp.get('type') == 'pong':
                    print(f"Found Editor Node: {resp.get('node_id')} at {addr[0]}")
                    # Usually 'pong' contains the 'command_port'
                    # Or sometimes we have to interpret "command_socket"
                    # Let's inspect the response to be sure
                    tcp_port = resp.get('command_port')
                    tcp_host = addr[0]
                    
                    if tcp_port:
                        print(f"Discovered TCP Command Port: {tcp_port}")
                        break
            except socket.timeout:
                pass
                
    except Exception as e:
        print(f"Discovery Error: {e}")
    finally:
        sock.close()

    # If UDP failed, try default static port fallback (just in case)
    if not tcp_port:
        print("UDP Discovery timed out. Trying default TCP port 6766...")
        tcp_host = '127.0.0.1'
        tcp_port = 6766

    return execute_via_tcp_magic(tcp_host, tcp_port, file_path)

def execute_via_tcp_magic(host, port, file_path):
    print(f"Connecting to TCP {host}:{port}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
            
        # Command Message (With MAGIC)
        command_data = {
            "magic": "ue_py",
            "version": 1,
            "type": "command",
            "command": script_content
        }
            
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            
            # Send JSON payload
            payload = json.dumps(command_data).encode('utf-8')
            s.sendall(payload)
            print("Script sent! Waiting for execution report...")
            
            # Receive response
            response = s.recv(4096)
            if response:
                print(f"Response: {response.decode('utf-8')}")
                return True
            else:
                print("No response received (but connection was made).")
                return True
            
    except ConnectionRefusedError:
        print(f"FAILED: Connection refused on {host}:{port}. Is the Editor running with 'Remote Execution' enabled?")
        return False
    except Exception as e:
        print(f"TCP Execution Error: {e}")
        # Identify if it was a magic error
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Test mode
        test_file = "TempMagicTest.py"
        with open(test_file, "w") as f:
            f.write("import unreal\nunreal.log_warning('AGENT: Magic Protocl Connection Successful!')")
        remote_exec_magic(test_file)
        try: os.remove(test_file) 
        except: pass
    else:
        remote_exec_magic(sys.argv[1])
