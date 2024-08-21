const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const net = require('net');
const { match } = require('assert');
const { exit } = require('process');
const path = require('path');
const { isErrored } = require('stream');

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
    {id: 1, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 2, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 3, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 4, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 5, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 6, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 7, isEnabled: null, layer: null, capability: null, screen: null, pipes: []},
    {id: 8, isEnabled: null, layer: null, capability: null, screen: null, pipes: []}
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
const regex_active_screens =    /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/status\/@props\/mode/;
const regex_active_layers =     /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/status\/@props\/layerCount/;
const regex_screen_optimized =  /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/status\/@props\/isOptimized/;
const regex_layer_capability =  /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/\$layer\/@items\/([0-9]+)\/status\/@props\/capability/;
const regex_layer_regions =     /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/\$layer\/@items\/([0-9]+)\/status\/@props\/usedInRegions/;
const regex_layer_mask =        /DeviceObject\/preconfig\/resources\/new\/\$screen\/@items\/S([0-9]+)\/\$layer\/@items\/([0-9]+)\/status\/@props\/canUseMask/;
const regex_scaler =            /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/isEnabled/;
const regex_pipe =              /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/scalerAllocation\/@props\/usedOnOutPipe([1-8])/;
const regex_layer =             /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/usedInLayer/;
const regex_scaler_screen =     /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/usedInScreen/;
const regex_capability =        /DeviceObject\/preconfig\/resources\/new\/status\/mapping\/\$device\/@items\/([1-4])\/\$vpuLayer\/@items\/PROC_([1-4])_SCALER_([1-8])\/@props\/capability/;
const regex_device_type =       /DeviceObject\/system\/\$device\/@items\/([1-4])\/@props\/dev/;

const empty_devices_list = [
    {id: 1, vpu: []},
    {id: 2, vpu: []},
    {id: 3, vpu: []},
    {id: 4, vpu: []}
]

const empty_screens_list = [
    {id: 1, active: false, optimized: false, layers: []},
    {id: 2, active: false, optimized: false, layers: []},
    {id: 3, active: false, optimized: false, layers: []},
    {id: 4, active: false, optimized: false, layers: []},
    {id: 5, active: false, optimized: false, layers: []},
    {id: 6, active: false, optimized: false, layers: []},
    {id: 7, active: false, optimized: false, layers: []},
    {id: 8, active: false, optimized: false, layers: []},
    {id: 9, active: false, optimized: false, layers: []},
    {id: 10, active: false, optimized: false, layers: []},
    {id: 11, active: false, optimized: false, layers: []},
    {id: 12, active: false, optimized: false, layers: []},
    {id: 13, active: false, optimized: false, layers: []},
    {id: 14, active: false, optimized: false, layers: []},
    {id: 15, active: false, optimized: false, layers: []},
    {id: 16, active: false, optimized: false, layers: []},
    {id: 17, active: false, optimized: false, layers: []},
    {id: 18, active: false, optimized: false, layers: []},
    {id: 19, active: false, optimized: false, layers: []},
    {id: 20, active: false, optimized: false, layers: []},
    {id: 21, active: false, optimized: false, layers: []},
    {id: 22, active: false, optimized: false, layers: []},
    {id: 23, active: false, optimized: false, layers: []},
    {id: 24, active: false, optimized: false, layers: []}
]

var devices;
var screens;

function connectAWJ() {
    awj = new net.Socket();

    devices = JSON.parse(JSON.stringify(empty_devices_list));
    screens = JSON.parse(JSON.stringify(empty_screens_list));

    console.log(`Connecting to ${tcp_ip} on port ${tcp_port}`);

    awj.connect(tcp_port, tcp_ip, () => {
        console.log('Connected to TCP server');
        io.emit("message", JSON.stringify({"type": "info", "title": "Connected", "content": ""}));

        
        // First we get enabled screens and their data
        for(let screen = 1; screen <= 24; screen++) {
            message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/\$screen/@items/S${screen}/status/@props/mode"}`
            awj.write(message + eotChar);
        }

        setTimeout(function() {
            // Then we get connected devices and their data
            // TODO: ensure this part is executed AFTER we got all screen info
            io.emit("message", JSON.stringify({"type": "info", "title": "Connected", "content": "Getting device list"}));
            for(let device = 1; device <= 4; device++) {
                message = `{"op":"get","path":"DeviceObject/system/$device/@items/${device}/@props/dev"}`;
                awj.write(message + eotChar);
            }
        }, 0);
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
            if(jsonObject.path == undefined) {
                console.log("JSON ERROR: ###############################################")
                console.log(JSON.stringify(jsonObject))
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
                    getDevicesUsage();
                }
                return;
            }
            

            
            
            const match_active_screens = jsonObject.path.match(regex_active_screens);
            const match_active_layers = jsonObject.path.match(regex_active_layers);
            const match_screen_optimized = jsonObject.path.match(regex_screen_optimized);
            const match_layer_capability = jsonObject.path.match(regex_layer_capability);
            const match_layer_regions = jsonObject.path.match(regex_layer_regions);
            const match_layer_mask = jsonObject.path.match(regex_layer_mask);
            const match_scaler = jsonObject.path.match(regex_scaler);
            const match_scaler_screen = jsonObject.path.match(regex_scaler_screen);
            const match_pipe = jsonObject.path.match(regex_pipe);
            const match_layer = jsonObject.path.match(regex_layer);
            const match_capability = jsonObject.path.match(regex_capability);
            
            //
            // THE FOLLOWING SHOULD BE THE FIRST MESSAGES TO BE REPLIED BY THE AQUILON
            // Here we are getting the screens settings (active, layers, optimized...)
            //
            if (match_active_screens) {
                const screenId = match_active_screens[1];
                let screen = screens.find(s => s.id == screenId);
                screen.active = jsonObject.value != 'DISABLED';
                // If screen is active, get additional indo
                if(screen.active) {
                    // Get active layer count
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/\$screen/@items/S${screenId}/status/@props/layerCount"}`
                    awj.write(message + eotChar);
                    // Get optimized status
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/$screen/@items/S${screenId}/status/@props/isOptimized"}`
                    awj.write(message + eotChar);
                }
            } else if(match_screen_optimized) {
                const screenId = match_screen_optimized[1];
                let screen = screens.find(s => s.id == screenId);
                screen.optimized = jsonObject.value;
            } else if (match_active_layers) {
                const screenId = match_active_layers[1];
                let screen = screens.find(s => s.id == screenId);
                const active_layers = jsonObject.value;
                /*let newArr = []
                for(let id = 1; id <= active_layers; id++) {
                    newArr.push({id: id, capability: undefined, mask: false})
                }*/
                screen.layers = [];
                for(let layer = 1; layer <= active_layers; layer++) {
                    screen.layers.push({id: layer, capability: undefined, regions: [], mask: false})
                    // Get layer capacity
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/$screen/@items/S${screenId}/$layer/@items/${layer}/status/@props/capability"}`
                    awj.write(message + eotChar);
                    // Get layer regions
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/$screen/@items/S${screenId}/$layer/@items/${layer}/status/@props/usedInRegions"}`
                    awj.write(message + eotChar);
                    // Get layer masking active
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/$screen/@items/S${screenId}/$layer/@items/${layer}/status/@props/canUseMask"}`
                    awj.write(message + eotChar);
                }
            } else if(match_layer_capability) {
                const screenId = match_layer_capability[1];
                let screen = screens.find(s => s.id == screenId);
                const layerId = match_layer_capability[2];
                let layer = screen.layers.find(l => l.id == layerId);
                layer.capability = jsonObject.value;
            } else if(match_layer_regions) {
                const screenId = match_layer_regions[1];
                let screen = screens.find(s => s.id == screenId);
                const layerId = match_layer_regions[2];
                let layer = screen.layers.find(l => l.id == layerId);
                layer.regions = jsonObject.value;
            } else if(match_layer_mask) {
                const screenId = match_layer_mask[1];
                let screen = screens.find(s => s.id == screenId);
                const layerId = match_layer_mask[2];
                let layer = screen.layers.find(l => l.id == layerId);
                layer.mask = jsonObject.value;
            } 
            //
            // FROM HERE IT DOESN'T MATTER IN WHICH ORDER THE MESSAGES ARRIVE
            // this is because we already have the array of screens, layers, capabilities and masking
            //
            else if (match_scaler) {
                const deviceId = match_scaler[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_scaler[2]; // PROC_#
                const scaler = match_scaler[3]; // SCALER_#
                let vpu = getVpu(device, proc);
                let isEnabled = jsonObject.value;
                vpu.scalers[scaler-1].isEnabled = isEnabled;
                if(isEnabled) {
                    // Get which screen is processed by this scaler
                    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/${deviceId}/$vpuLayer/@items/PROC_${proc}_SCALER_${scaler}/@props/usedInScreen"}`
                    awj.write(message + eotChar);
                }
            } else if(match_scaler_screen) {
                const deviceId = match_scaler_screen[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_scaler_screen[2]; // PROC_#
                const scaler = match_scaler_screen[3]; // SCALER_#
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].screen = jsonObject.value.substring(1); // The value is "S#", we remove the initial S from the screen number
            } else if (match_pipe) {
                const deviceId = match_pipe[1];
                let device = devices.find(d => d.id == deviceId);
                const proc = match_pipe[2]; // PROC_#
                const scaler = match_pipe[3]; // SCALER_#
                const pipe = match_pipe[4]; // PIPE_#
                let vpu = getVpu(device, proc);
                vpu.scalers[scaler-1].pipes[pipe] = jsonObject.value;// != 'NONE';
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
        checkAndSendData();
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
        } else if(message.type == "recheckScaler") {
            // We are missing some data about a single scaler, check everything again
            let device = devices.find(d => d.id == message.options.deviceId);
            getScalerUsage(device, message.options.procId, message.options.scalerId);
            //console.log("RECHECKING SCALER " + device.id + "/" + message.options.procId + "/" + message.options.scalerId)
        } else if(message.type == "recheckVPU") {
            // Looks like this processor is totally missing
            let device = devices.find(d => d.id == message.options.deviceId);
            getVPUUsage(device, message.options.procId);
            //console.log("RECHECKING VPU " + device.id + "/" + message.options.procId)
        } else if(message.type == "recheckPipe") {
            // Looks like we miss some data for a specific pipe
            let device = devices.find(d => d.id == message.options.deviceId);
            //getVPUUsage(device, message.options.procId);
            getScalerPipeUsage(device, message.options.procId, message.options.scalerId, message.options.pipeId);
            //console.log("RECHECKING PIPE " + device.id + "/" + message.options.procId + "/" + message.options.scalerId + "/" + message.options.pipeId)
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

function getDevicesUsage() {
    console.log("Getting VPU usage");

    devices.forEach(device => {
        getDeviceUsage(device);
    });
}

function getDeviceUsage(device) {
    for(let vpu = 1; vpu <= device.vpus; vpu++) {
        getVPUUsage(device, vpu);
    }
}

function getVPUUsage(device, vpu) {
    for(scaler = 1; scaler <=8; scaler++) {
        getScalerUsage(device, vpu, scaler);
    }
}

function getScalerUsage(device, vpu, scaler) {
    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/isEnabled"}`;
    awj.write(message + eotChar);
    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/usedInLayer"}`;
    awj.write(message + eotChar);
    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/@props/capability"}`;
    awj.write(message + eotChar);
    for(pipe = 1; pipe <= 8; pipe++) { //TODO: get only the needed pipes
        getScalerPipeUsage(device, vpu, scaler, pipe);
    }
}

function getScalerPipeUsage(device, vpu, scaler, pipe) {
    message = `{"op":"get","path":"DeviceObject/preconfig/resources/new/status/mapping/\$device/@items/${device.id}/\$vpuLayer/@items/PROC_${vpu}_SCALER_${scaler}/scalerAllocation/@props/usedOnOutPipe${pipe}"}`;
    awj.write(message + eotChar);
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

function checkAndSendData() {
    /*
    let errorCounter = 0;
    // Validate screens
    //console.log(screens);

    // Validate VPUs 
    //console.log(devices)
    if(!devices) {
        //console.error("MISSING DEVICES")
        return;
    }
    devices.forEach(device => {
        if(device.vpu.length != device.vpus) {
            //console.error("MISSING VPU DATA")
            return;
        }
    
        console.log("VPU OK")
        device.vpu.forEach(vpu => {
            vpu.scalers.forEach(scaler => {
                if(typeof scaler.isEnabled != 'boolean') {
                    // Error missing scaler enabled
                    errorCounter++;
                }
                if(typeof scaler.layer != 'number') {
                    // Error missing layer number
                    errorCounter++;
                }
                if(typeof scaler.capability != 'string') {
                    // Error missing layer capability
                    errorCounter++;
                }
                scaler.pipes.forEach(pipe => {
                    if(parseInt(pipe) == NaN && pipe != 'NONE') {
                        console.log(pipe)
                        // Error missing pipe data
                        errorCounter++;
                    }
                })
            })
        });
    });
    console.log(errorCounter)
    */
    io.emit('receiveScreens', JSON.stringify(screens));
    io.emit('receiveVPU', JSON.stringify(devices));
}