const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const net = require('net');
const { match } = require('assert');
const { exit } = require('process');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);
const eotChar = '\u0004';

var tcp_ip = '192.168.2.140'; // Replace with your TCP host
var tcp_port = 10606; // Replace with your TCP port

app.use(express.static(path.join(__dirname, 'public/')));

// Serve the static HTML file
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public/index.html'));
});

var awj = null;

const empty_proc = [
    {id: 1, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 2, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 3, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 4, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 5, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 6, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 7, isEnabled: false, layer: false, capability: false, pipes: []},
    {id: 8, isEnabled: false, layer: false, capability: false, pipes: []}
]

const device_vpus = {
    RSALPHA: 1,
    RS1: 1,
    RS2: 2,
    RS3: 2,
    RS4: 3,
    RS5: 3,
    RS6: 4,
    C: 2,
    CPLUS: 3,
    CMAX: 4
}

// Regular expression to extract PROC_# and SCALER_#
const regex_scaler = /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/isEnabled/;
const regex_pipe = /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/scalerAllocation\/@props\/usedOnOutPipe([1-8])/;
const regex_layer = /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/usedInLayer/;
const regex_capability = /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/capability/;
const regex_device_type = /DeviceObject\/system\/\$device\/@items\/([1-4])\/@props\/dev/;

const empty_devices_list = [
    {id: 1, vpu: []},
    {id: 2, vpu: []},
    {id: 3, vpu: []},
    {id: 4, vpu: []}
]

var devices;

function connectAWJ() {
    awj = new net.Socket();

    devices = JSON.parse(JSON.stringify(empty_devices_list));

    console.log(`Connecting to ${tcp_ip} on port ${tcp_port}`);

    awj.connect(tcp_port, tcp_ip, () => {
        console.log('Connected to TCP server');
        io.emit("message", JSON.stringify({"type": "info", "title": "Connected", "content": ""}));

        io.emit("message", JSON.stringify({"type": "info", "title": "Connected", "content": "Getting device list"}));
        // Get connected devices
        for(device = 1; device <= 4; device++) {
            message = `{"op":"get","path":"DeviceObject/system/$device/@items/${device}/@props/dev"}`;
            awj.write(message + eotChar);
        }
    });

    awj.on('data', (data) => {
        const pieces = data.toString().split(eotChar);
        pieces.forEach(data => {
            let jsonObject
            try {
                jsonObject = JSON.parse(data);
            } catch(error) {
            }

            if(jsonObject == undefined || jsonObject == {}) {
                return;
            }
            //const matches = data.match(regex_device_type);
            let matches = jsonObject.path.match(regex_device_type);
            if (matches) {
                const deviceId = matches[1]; // Device ID
                let device = devices.find(d => d.id == deviceId);
                device.type = jsonObject.value.substring(4);
                device.vpus = device_vpus[device.type];

                if(devices.every(d => d.hasOwnProperty('type'))) {
                    //console.log(JSON.stringify(devices));
                    getVPUUsage();
                }
                return;
            }
            

            
            

            const match_scaler = jsonObject.path.match(regex_scaler);
            const match_pipe = jsonObject.path.match(regex_pipe);
            const match_layer = jsonObject.path.match(regex_layer);
            const match_capability = jsonObject.path.match(regex_capability);
            

            if (match_scaler) {
                const deviceId = match_scaler[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_scaler[2]; // PROC_#
                const scaler = match_scaler[3]; // SCALER_#
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].isEnabled = jsonObject.value;
            } else if (match_pipe) {
                const deviceId = match_pipe[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_pipe[2]; // PROC_#
                const scaler = match_pipe[3]; // SCALER_#
                const pipe = match_pipe[4]; // PIPE_#
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].pipes[pipe] = jsonObject.value != 'NONE';
            } else if (match_layer) {
                const deviceId = match_layer[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_layer[2]; // PROC_#
                const scaler = match_layer[3]; // SCALER_#
                let layer = 0;
                if(jsonObject.value == 'NATIVE') {
                    layer = 1;
                } else {
                    layer = parseInt(jsonObject.value) + 1;
                }
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].layer = layer;
            } else if (match_capability) {
                const deviceId = match_capability[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_capability[2]; // PROC_#
                const scaler = match_capability[3]; // SCALER_#
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].capability = jsonObject.value;
            } else {
                //console.log("No match found.");
            }
        });
        io.emit('receiveVPU', JSON.stringify(devices));
        //console.log(devices)
    });

    awj.on('close', () => {
        console.log('Connection closed');
        //setTimeout(connectToTcpServer, 5000); // Attempt to reconnect after 5 seconds
    });

    awj.on('error', (err) => {
        console.error('TCP error: ' + err.message);
        io.emit("message", JSON.stringify({"type": "error", "title": "TCP error", "content": "Check IP/port\n" + err.message}));

        io.emit('receiveMessage', 'Error: ' + err.message);
        awj.destroy(); // Close the connection on error
    });
}

io.on('connection', (socket) => {
    console.log('A web user is connected');

    socket.on('sendMessage', (message) => {
        message = JSON.parse(message);
        
        if(message.type == "connect") {
            console.log("Connecting...");
            io.emit("message", JSON.stringify({"type": "warning", "title": "Connecting...", "content": ""}));
            if (awj) {
                console.log("Destroying previous connection");
                awj.destroy();
            }
            
            validIpAddressRegex = new RegExp("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$");
            //validHostnameRegex = new RegExp("^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$");
            message.options.port = parseInt(message.options.port);
            if(validIpAddressRegex.test(message.options.ip) && message.options.port > 0 && message.options.port < 65536) {
                tcp_ip = message.options.ip;
                tcp_port = message.options.port;
                connectAWJ();
            } else {
                console.log("Invalid host/IP or TCP port number");
                io.emit("message", JSON.stringify({"type": "error", "title": "Wrong settings", "content": "Host/IP and port are not valid"}));
            }
        }
    });

    socket.on('disconnect', () => {
        console.log('User disconnected');
    });
});

const PORT = 15566;
server.listen(PORT, () => {
    console.log(`Server is running, open a web browser at http://localhost:${PORT}`);
    // Open the default web browser and display the main page
    require('child_process').exec(`start http://localhost:${PORT}`);
});

function getVPUUsage(deviceId) {
    console.log("Getting VPU usage");

    devices.forEach(device => {
        for(let vpu = 1; vpu <= device.vpus; vpu++) {
            for(scaler = 1; scaler <=8; scaler++) {
                message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/isEnabled"}`;
                awj.write(message + eotChar);
                message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/usedInLayer"}`;
                awj.write(message + eotChar);
                message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/capability"}`;
                awj.write(message + eotChar);
                for(pipe = 1; pipe <= 8; pipe++) { //TODO: get only the needed pipes
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/scalerAllocation/@props/usedOnOutPipe${pipe}"}`;
                    awj.write(message + eotChar);
                }
            }
        }
    });
}

function getVpu(device, vpu_id) {
    let vpu = device.vpu.find(v => v.vpu_id == vpu_id);
    if(vpu == undefined) {
        device.vpu.push({
            vpu_id: vpu_id,
            scalers: JSON.parse(JSON.stringify(empty_proc))
        });
    }
    return device.vpu.find(v => v.vpu_id == vpu_id);
}