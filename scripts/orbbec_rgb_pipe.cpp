#include <OpenNI.h>

#include <atomic>
#include <csignal>
#include <cstdio>
#include <iostream>

namespace {

std::atomic<bool> running{true};

void stop_running(int) {
    running = false;
}

}  // namespace

int main() {
    std::signal(SIGINT, stop_running);
    std::signal(SIGTERM, stop_running);
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    if(openni::OpenNI::initialize() != openni::STATUS_OK) {
        std::cerr << "OpenNI initialize failed: " << openni::OpenNI::getExtendedError() << "\n";
        return 1;
    }

    openni::Array<openni::DeviceInfo> devices;
    openni::OpenNI::enumerateDevices(&devices);
    if(devices.getSize() == 0) {
        std::cerr << "No OpenNI camera found\n";
        openni::OpenNI::shutdown();
        return 2;
    }

    openni::Device device;
    if(device.open(devices[0].getUri()) != openni::STATUS_OK) {
        std::cerr << "OpenNI device open failed: " << openni::OpenNI::getExtendedError() << "\n";
        openni::OpenNI::shutdown();
        return 3;
    }

    const auto *sensor_info = device.getSensorInfo(openni::SENSOR_COLOR);
    if(sensor_info == nullptr) {
        std::cerr << "OpenNI color sensor is unavailable\n";
        device.close();
        openni::OpenNI::shutdown();
        return 4;
    }

    openni::VideoStream stream;
    if(stream.create(device, openni::SENSOR_COLOR) != openni::STATUS_OK) {
        std::cerr << "OpenNI color stream create failed: " << openni::OpenNI::getExtendedError() << "\n";
        device.close();
        openni::OpenNI::shutdown();
        return 5;
    }

    bool selected_mode = false;
    const auto &modes = sensor_info->getSupportedVideoModes();
    for(int index = 0; index < modes.getSize(); ++index) {
        const auto &mode = modes[index];
        if(mode.getResolutionX() == 640 && mode.getResolutionY() == 480 &&
           mode.getFps() == 30 && mode.getPixelFormat() == openni::PIXEL_FORMAT_RGB888) {
            if(stream.setVideoMode(mode) == openni::STATUS_OK) selected_mode = true;
            break;
        }
    }
    if(!selected_mode) {
        std::cerr << "RGB888 640x480@30 mode is unavailable\n";
        stream.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 6;
    }

    // Mirroring invalidates ArUco bit patterns and table coordinates.
    stream.setMirroringEnabled(false);
    if(stream.start() != openni::STATUS_OK) {
        std::cerr << "OpenNI color stream start failed: " << openni::OpenNI::getExtendedError() << "\n";
        stream.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 7;
    }

    constexpr int width = 640;
    constexpr int height = 480;
    constexpr int row_bytes = width * 3;
    while(running) {
        openni::VideoFrameRef frame;
        if(stream.readFrame(&frame) != openni::STATUS_OK || !frame.isValid()) continue;
        if(frame.getWidth() != width || frame.getHeight() != height ||
           frame.getVideoMode().getPixelFormat() != openni::PIXEL_FORMAT_RGB888) {
            std::cerr << "Unexpected OpenNI color frame format\n";
            break;
        }
        const auto *data = static_cast<const unsigned char *>(frame.getData());
        const int stride = frame.getStrideInBytes();
        if(stride == row_bytes) {
            if(std::fwrite(data, 1, row_bytes * height, stdout) != static_cast<std::size_t>(row_bytes * height)) break;
        } else {
            for(int row = 0; row < height; ++row) {
                if(std::fwrite(data + row * stride, 1, row_bytes, stdout) != static_cast<std::size_t>(row_bytes)) {
                    running = false;
                    break;
                }
            }
        }
    }

    stream.stop();
    stream.destroy();
    device.close();
    openni::OpenNI::shutdown();
    return 0;
}
