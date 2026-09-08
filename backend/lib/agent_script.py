def build_agent_script(server_url: str, token: str, agent_id: str) -> str:
    return f'''#!/usr/bin/env python3
"""Cyber Oracle cross-platform metadata agent. Run with Admin/root; payload bytes are never sent."""
import json, os, socket, struct, time, urllib.request
from datetime import datetime, timezone

SERVER_URL = os.environ.get("CYBER_ORACLE_URL", {server_url!r}).rstrip("/")
AGENT_TOKEN = os.environ.get("CYBER_ORACLE_TOKEN", {token!r})
AGENT_ID = {agent_id!r}
BATCH_SIZE = 25

def tcp_flags(value):
    names = [(1,"FIN"),(2,"SYN"),(4,"RST"),(8,"PSH"),(16,"ACK"),(32,"URG"),(64,"ECE"),(128,"CWR")]
    return "|".join(name for bit, name in names if value & bit)

def parse_packet(data, interface, os_name):
    offset = 0
    if os_name != "nt":
        if len(data) < 34 or struct.unpack("!H", data[12:14])[0] != 0x0800:
            return None
        offset = 14
    else:
        if len(data) < 20:
            return None
            
    version_ihl = data[offset]
    if version_ihl >> 4 != 4:
        return None
    ihl = (version_ihl & 15) * 4
    if len(data) < offset + ihl:
        return None
    total_length = struct.unpack("!H", data[offset+2:offset+4])[0]
    ttl = data[offset+8]
    protocol_number = data[offset+9]
    source = socket.inet_ntoa(data[offset+12:offset+16])
    destination = socket.inet_ntoa(data[offset+16:offset+20])
    transport = offset + ihl
    source_port = destination_port = None
    flags = ""
    protocol = {{6:"TCP", 17:"UDP", 1:"ICMP"}}.get(protocol_number, f"IP-{{protocol_number}}")
    if protocol_number in (6, 17) and len(data) >= transport + 4:
        source_port, destination_port = struct.unpack("!HH", data[transport:transport+4])
    if protocol_number == 6 and len(data) >= transport + 14:
        flags = tcp_flags(data[transport+13])
    return {{"timestamp":datetime.now(timezone.utc).isoformat(),"interface":interface,"source":source,"destination":destination,"source_port":source_port,"destination_port":destination_port,"protocol":protocol,"tcp_flags":flags,"packet_size":total_length,"ttl":ttl}}

def send(events):
    request = urllib.request.Request(SERVER_URL + "/api/supervision/ingest", data=json.dumps(events).encode(), headers={{"Content-Type":"application/json","X-Agent-Token":AGENT_TOKEN}}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status

def main():
    os_name = os.name
    interface = os.environ.get("CYBER_ORACLE_INTERFACE", "all")
    
    if os_name == "nt":
        import ctypes, sys
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("Administrator privileges required for raw socket capture. Requesting UAC elevation...")
            script = os.path.abspath(sys.argv[0])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{{script}}"', None, 1)
            return

    try:
        if os_name == "nt":
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
            sock.bind((local_ip, 0))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
            print(f"Cyber Oracle agent {{AGENT_ID}} capturing metadata on Windows ({{local_ip}}); payloads are discarded")
        else:
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))
            print(f"Cyber Oracle agent {{AGENT_ID}} capturing metadata on {{interface}}; payloads are discarded")
    except OSError as e:
        print(f"Error initializing raw socket: {{e}}")
        print("Make sure you are running this script as Administrator (Windows) or root (Linux).")
        return
        
    batch, last_send = [], time.time()
    try:
        while True:
            packet, address = sock.recvfrom(65535)
            addr_str = address[0] if isinstance(address, tuple) else str(address)
            event = parse_packet(packet, addr_str, os_name)
            if event:
                batch.append(event)
            if batch and (len(batch) >= BATCH_SIZE or time.time() - last_send >= 1.0):
                try:
                    send(batch)
                    print(f"sent {{len(batch)}} metadata events")
                    batch.clear()
                except Exception as exc:
                    print("send failed:", exc)
                    if len(batch) > 500:
                        batch = batch[-500:]
                last_send = time.time()
    except KeyboardInterrupt:
        print("Stopping capture...")
    finally:
        if os_name == "nt" and 'sock' in locals():
            sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)

if __name__ == "__main__":
    main()
'''