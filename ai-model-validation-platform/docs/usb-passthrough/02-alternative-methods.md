# Alternative USB Passthrough Methods

While USB/IP is the recommended approach, alternative methods may be necessary for specific use cases or when USB/IP is not available.

## Table of Contents

1. [Bridge Service Method](#bridge-service-method)
2. [Direct Windows Backend](#direct-windows-backend)
3. [Virtual Machine Passthrough](#virtual-machine-passthrough)
4. [Network-Based Solutions](#network-based-solutions)
5. [Comparison Matrix](#comparison-matrix)

## Bridge Service Method

A custom Windows service that creates a bridge between LabJack devices and containerized applications.

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Container     │◄──►│  Bridge Service │◄──►│  LabJack Device │
│   (Linux)       │    │   (Windows)     │    │   (Hardware)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Implementation

#### 1. Bridge Service (C#)

Create `LabJackBridgeService.cs`:

```csharp
using System;
using System.ServiceProcess;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json;

namespace LabJackBridge
{
    public partial class LabJackBridgeService : ServiceBase
    {
        private TcpListener _listener;
        private Thread _listenerThread;
        private bool _isRunning;
        
        public LabJackBridgeService()
        {
            InitializeComponent();
            ServiceName = "LabJackBridge";
        }

        protected override void OnStart(string[] args)
        {
            _isRunning = true;
            _listener = new TcpListener(IPAddress.Any, 9999);
            _listener.Start();
            
            _listenerThread = new Thread(HandleClients);
            _listenerThread.Start();
            
            EventLog.WriteEntry("LabJack Bridge Service started");
        }

        protected override void OnStop()
        {
            _isRunning = false;
            _listener?.Stop();
            _listenerThread?.Join(5000);
            
            EventLog.WriteEntry("LabJack Bridge Service stopped");
        }

        private void HandleClients()
        {
            while (_isRunning)
            {
                try
                {
                    var client = _listener.AcceptTcpClient();
                    var clientThread = new Thread(() => ProcessClient(client));
                    clientThread.Start();
                }
                catch (Exception ex)
                {
                    EventLog.WriteEntry($"Error accepting client: {ex.Message}");
                }
            }
        }

        private void ProcessClient(TcpClient client)
        {
            try
            {
                var stream = client.GetStream();
                var buffer = new byte[4096];
                
                while (client.Connected)
                {
                    int bytesRead = stream.Read(buffer, 0, buffer.Length);
                    if (bytesRead == 0) break;
                    
                    string request = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    string response = ProcessLabJackCommand(request);
                    
                    byte[] responseBytes = Encoding.UTF8.GetBytes(response);
                    stream.Write(responseBytes, 0, responseBytes.Length);
                }
            }
            catch (Exception ex)
            {
                EventLog.WriteEntry($"Client error: {ex.Message}");
            }
            finally
            {
                client?.Close();
            }
        }

        private string ProcessLabJackCommand(string request)
        {
            try
            {
                var command = JsonConvert.DeserializeObject<LabJackCommand>(request);
                
                // Initialize LabJack U3 connection
                using (var device = new U3())
                {
                    switch (command.Action.ToLower())
                    {
                        case "read":
                            return ReadAnalogInput(device, command.Channel);
                        case "write":
                            return WriteDigitalOutput(device, command.Channel, command.Value);
                        case "config":
                            return ConfigureDevice(device, command.Parameters);
                        default:
                            return JsonConvert.SerializeObject(new { error = "Unknown command" });
                    }
                }
            }
            catch (Exception ex)
            {
                return JsonConvert.SerializeObject(new { error = ex.Message });
            }
        }

        private string ReadAnalogInput(U3 device, int channel)
        {
            try
            {
                double voltage = device.GetAIN(channel);
                return JsonConvert.SerializeObject(new { success = true, voltage = voltage });
            }
            catch (Exception ex)
            {
                return JsonConvert.SerializeObject(new { error = ex.Message });
            }
        }

        private string WriteDigitalOutput(U3 device, int channel, double value)
        {
            try
            {
                device.SetDIO(channel, value > 0);
                return JsonConvert.SerializeObject(new { success = true });
            }
            catch (Exception ex)
            {
                return JsonConvert.SerializeObject(new { error = ex.Message });
            }
        }

        private string ConfigureDevice(U3 device, object parameters)
        {
            try
            {
                // Device configuration logic here
                return JsonConvert.SerializeObject(new { success = true });
            }
            catch (Exception ex)
            {
                return JsonConvert.SerializeObject(new { error = ex.Message });
            }
        }
    }

    public class LabJackCommand
    {
        public string Action { get; set; }
        public int Channel { get; set; }
        public double Value { get; set; }
        public object Parameters { get; set; }
    }
}
```

#### 2. Client Library (Python)

Create `labjack_bridge_client.py`:

```python
import socket
import json
import time
from typing import Optional, Dict, Any

class LabJackBridgeClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = None
    
    def connect(self) -> bool:
        """Connect to the bridge service"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the bridge service"""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the bridge service"""
        if not self.socket:
            raise ConnectionError("Not connected to bridge service")
        
        try:
            # Send command
            command_json = json.dumps(command)
            self.socket.send(command_json.encode('utf-8'))
            
            # Receive response
            response_data = self.socket.recv(4096)
            response = json.loads(response_data.decode('utf-8'))
            
            return response
        except Exception as e:
            raise RuntimeError(f"Command failed: {e}")
    
    def read_analog_input(self, channel: int) -> float:
        """Read analog input from specified channel"""
        command = {
            'Action': 'read',
            'Channel': channel
        }
        
        response = self._send_command(command)
        
        if 'error' in response:
            raise RuntimeError(f"Read failed: {response['error']}")
        
        return response['voltage']
    
    def write_digital_output(self, channel: int, value: bool) -> bool:
        """Write digital output to specified channel"""
        command = {
            'Action': 'write',
            'Channel': channel,
            'Value': 1.0 if value else 0.0
        }
        
        response = self._send_command(command)
        
        if 'error' in response:
            raise RuntimeError(f"Write failed: {response['error']}")
        
        return response['success']
    
    def configure_device(self, parameters: Dict[str, Any]) -> bool:
        """Configure device parameters"""
        command = {
            'Action': 'config',
            'Parameters': parameters
        }
        
        response = self._send_command(command)
        
        if 'error' in response:
            raise RuntimeError(f"Configuration failed: {response['error']}")
        
        return response['success']

# Example usage
def main():
    client = LabJackBridgeClient()
    
    try:
        if client.connect():
            print("Connected to LabJack bridge service")
            
            # Read analog input from channel 0
            voltage = client.read_analog_input(0)
            print(f"Channel 0 voltage: {voltage:.3f}V")
            
            # Toggle digital output
            client.write_digital_output(4, True)
            time.sleep(1)
            client.write_digital_output(4, False)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
```

#### 3. Service Installation

Create `install_service.ps1`:

```powershell
# Build the service
dotnet build -c Release

# Install service
$servicePath = "$(Get-Location)\bin\Release\net6.0\LabJackBridge.exe"
New-Service -Name "LabJackBridge" -BinaryPathName $servicePath -DisplayName "LabJack Bridge Service"

# Set service to auto-start
Set-Service -Name "LabJackBridge" -StartupType Automatic

# Start service
Start-Service -Name "LabJackBridge"

Write-Host "LabJack Bridge Service installed and started successfully"
```

### Advantages
- Works in any environment
- Low latency communication
- Custom protocol optimization
- Full control over device access

### Disadvantages
- Requires custom development
- Service maintenance overhead
- Windows-only solution
- Potential security risks

## Direct Windows Backend

Run the entire application on Windows and use containers only for specific components.

### Architecture

```
┌─────────────────────────────────────────────┐
│              Windows Host                   │
│  ┌─────────────────┐  ┌─────────────────┐   │
│  │  Main App       │  │  Container      │   │
│  │  (LabJack)      │◄─┤  (Processing)   │   │
│  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────┘
```

### Implementation

#### 1. Windows Application

Create `LabJackApp.exe` using .NET:

```csharp
using System;
using System.Threading.Tasks;
using Docker.DotNet;
using Docker.DotNet.Models;

namespace LabJackApp
{
    class Program
    {
        private static DockerClient _dockerClient;
        
        static async Task Main(string[] args)
        {
            // Initialize Docker client
            _dockerClient = new DockerClientConfiguration().CreateClient();
            
            // Initialize LabJack
            using (var labjack = new U3())
            {
                Console.WriteLine("LabJack connected successfully");
                
                // Start processing container
                await StartProcessingContainer();
                
                // Main data acquisition loop
                while (true)
                {
                    // Read data from LabJack
                    var data = ReadSensorData(labjack);
                    
                    // Send data to container for processing
                    await SendDataToContainer(data);
                    
                    await Task.Delay(1000); // 1Hz sampling
                }
            }
        }
        
        private static SensorData ReadSensorData(U3 device)
        {
            return new SensorData
            {
                Timestamp = DateTime.UtcNow,
                Channel0 = device.GetAIN(0),
                Channel1 = device.GetAIN(1),
                Channel2 = device.GetAIN(2),
                Channel3 = device.GetAIN(3)
            };
        }
        
        private static async Task StartProcessingContainer()
        {
            var createParams = new CreateContainerParameters
            {
                Image = "data-processor:latest",
                ExposedPorts = new Dictionary<string, EmptyStruct>
                {
                    { "8080/tcp", new EmptyStruct() }
                },
                HostConfig = new HostConfig
                {
                    PortBindings = new Dictionary<string, IList<PortBinding>>
                    {
                        {
                            "8080/tcp",
                            new List<PortBinding>
                            {
                                new PortBinding { HostPort = "8080" }
                            }
                        }
                    }
                }
            };
            
            var container = await _dockerClient.Containers.CreateContainerAsync(createParams);
            await _dockerClient.Containers.StartContainerAsync(container.ID, new ContainerStartParameters());
            
            Console.WriteLine("Processing container started");
        }
        
        private static async Task SendDataToContainer(SensorData data)
        {
            using (var client = new HttpClient())
            {
                var json = JsonConvert.SerializeObject(data);
                var content = new StringContent(json, Encoding.UTF8, "application/json");
                
                try
                {
                    await client.PostAsync("http://localhost:8080/process", content);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Failed to send data: {ex.Message}");
                }
            }
        }
    }
    
    public class SensorData
    {
        public DateTime Timestamp { get; set; }
        public double Channel0 { get; set; }
        public double Channel1 { get; set; }
        public double Channel2 { get; set; }
        public double Channel3 { get; set; }
    }
}
```

#### 2. Container Application

Create processing container with `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "processor.py"]
```

Create `processor.py`:

```python
from flask import Flask, request, jsonify
import numpy as np
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/process', methods=['POST'])
def process_data():
    try:
        data = request.json
        
        # Extract sensor values
        values = [
            data['Channel0'],
            data['Channel1'], 
            data['Channel2'],
            data['Channel3']
        ]
        
        # Perform processing
        result = {
            'timestamp': data['Timestamp'],
            'average': np.mean(values),
            'std_dev': np.std(values),
            'min_value': np.min(values),
            'max_value': np.max(values)
        }
        
        logging.info(f"Processed data: {result}")
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Processing error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Advantages
- Native device access
- High performance
- Simple deployment
- Reliable connection

### Disadvantages
- Windows dependency
- Limited containerization benefits
- Harder to scale
- Development environment constraints

## Virtual Machine Passthrough

Configure USB passthrough in virtual machine environments.

### VMware Workstation/Player

#### Enable USB Passthrough

1. **Configure VM Settings**:
   - Power off the VM
   - Go to VM Settings > Hardware
   - Click "Add" > "USB Controller"
   - Select "USB 3.1" for best performance

2. **Add LabJack Device**:
   - Connect LabJack to host
   - In VM Settings > Hardware > USB Controller
   - Check "Show all USB input devices"
   - Add LabJack device to "Always connect to this virtual machine"

3. **VM Configuration File**:

```ini
# Add to .vmx file
usb.present = "TRUE"
usb.vbluetooth.startConnected = "TRUE"
usb.autoConnect.device0 = "0x0CD5:0x0009"
usb.autoConnect.device0.name = "LabJack U3"
usb_xhci.present = "TRUE"
usb_xhci.pciSlotNumber = "160"
```

#### Automation Script

Create `vmware-usb-setup.ps1`:

```powershell
param(
    [Parameter(Mandatory=$true)]
    [string]$VmxPath,
    [Parameter(Mandatory=$true)]
    [string]$DeviceVidPid
)

# Backup original VMX file
Copy-Item $VmxPath "$VmxPath.backup"

# Add USB configuration
$usbConfig = @"
usb.present = "TRUE"
usb.vbluetooth.startConnected = "TRUE"
usb.autoConnect.device0 = "$DeviceVidPid"
usb_xhci.present = "TRUE"
usb_xhci.pciSlotNumber = "160"
"@

Add-Content -Path $VmxPath -Value $usbConfig

Write-Host "USB passthrough configured for $DeviceVidPid"
```

### VirtualBox

#### Enable USB Support

1. **Install Extension Pack**:
   - Download VirtualBox Extension Pack
   - Install via File > Preferences > Extensions

2. **Configure USB Filter**:
   - VM Settings > Ports > USB
   - Enable USB Controller (USB 3.0)
   - Add USB filter for LabJack device

3. **Command Line Configuration**:

```bash
# Add USB filter
VBoxManage usbfilter add 0 --target "YourVM" --name "LabJack U3" --vendorid 0x0cd5 --productid 0x0009

# Enable USB 3.0
VBoxManage modifyvm "YourVM" --usbxhci on

# Set USB policy
VBoxManage modifyvm "YourVM" --usbehci on
```

### Advantages
- Complete OS isolation
- Multiple OS support
- Snapshot capability
- Easy backup/restore

### Disadvantages
- Performance overhead
- Complex setup
- Resource consumption
- Licensing considerations

## Network-Based Solutions

Share LabJack access over the network using dedicated protocols.

### USB/IP Over Network

Extend USB/IP to work across network boundaries:

```bash
# On Windows (server)
usbipd bind --busid 1-4
usbipd listen --address 0.0.0.0

# On Linux client
sudo modprobe usbip-core
sudo modprobe usbip-host
usbip attach --remote 192.168.1.100 --busid 1-4
```

### LabJack TCP Server

Create a dedicated TCP server for LabJack access:

```python
import socket
import threading
import u3
import json
import logging

class LabJackTCPServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.device = None
        self.server_socket = None
        self.running = False
        
    def start(self):
        try:
            # Initialize LabJack
            self.device = u3.U3()
            logging.info("LabJack U3 connected")
            
            # Start TCP server
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            logging.info(f"Server listening on {self.host}:{self.port}")
            
            while self.running:
                client_socket, address = self.server_socket.accept()
                logging.info(f"Client connected from {address}")
                
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.start()
                
        except Exception as e:
            logging.error(f"Server error: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_socket):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                try:
                    request = json.loads(data.decode('utf-8'))
                    response = self.process_request(request)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                except json.JSONDecodeError:
                    error_response = {'error': 'Invalid JSON'}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                    
        except Exception as e:
            logging.error(f"Client error: {e}")
        finally:
            client_socket.close()
    
    def process_request(self, request):
        try:
            command = request.get('command')
            
            if command == 'read_ain':
                channel = request.get('channel', 0)
                voltage = self.device.getAIN(channel)
                return {'success': True, 'voltage': voltage}
                
            elif command == 'set_dio':
                channel = request.get('channel')
                state = request.get('state')
                self.device.setDIOState(channel, state)
                return {'success': True}
                
            elif command == 'get_temperature':
                temp = self.device.getTemperature()
                return {'success': True, 'temperature': temp}
                
            else:
                return {'error': 'Unknown command'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.device:
            self.device.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = LabJackTCPServer()
    server.start()
```

## Comparison Matrix

| Method | Setup Complexity | Performance | Reliability | Security | Cross-Platform |
|--------|------------------|-------------|-------------|----------|----------------|
| USB/IP (usbipd-win) | Low | High | High | Medium | Yes |
| Bridge Service | High | Very High | Medium | Low | No |
| Direct Windows | Medium | Very High | Very High | High | No |
| VM Passthrough | High | Medium | High | High | Yes |
| Network Solutions | Medium | Medium | Medium | Low | Yes |

### Recommendations

- **Development**: USB/IP (usbipd-win)
- **Production**: Direct Windows Backend
- **Cross-platform**: Network-based solutions
- **High performance**: Bridge Service
- **Isolation**: VM Passthrough

## Next Steps

- See [Troubleshooting Guide](./03-troubleshooting.md) for common issues
- Review [Performance Optimization](./04-performance.md) for speed improvements
- Check [Security Considerations](./05-security.md) for best practices