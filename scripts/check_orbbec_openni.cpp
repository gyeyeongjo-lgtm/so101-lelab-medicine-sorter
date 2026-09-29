#include <OpenNI.h>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {

const char *sensor_name(openni::SensorType sensor) {
    switch(sensor) {
        case openni::SENSOR_COLOR: return "color";
        case openni::SENSOR_IR: return "ir";
        case openni::SENSOR_DEPTH: return "depth";
        default: return "unknown";
    }
}

const char *format_name(openni::PixelFormat format) {
    switch(format) {
        case openni::PIXEL_FORMAT_RGB888: return "RGB888";
        case openni::PIXEL_FORMAT_YUV422: return "YUV422";
        case openni::PIXEL_FORMAT_GRAY8: return "GRAY8";
        case openni::PIXEL_FORMAT_GRAY16: return "GRAY16";
        case openni::PIXEL_FORMAT_DEPTH_1_MM: return "DEPTH_1_MM";
        case openni::PIXEL_FORMAT_DEPTH_100_UM: return "DEPTH_100_UM";
        case openni::PIXEL_FORMAT_JPEG: return "JPEG";
        default: return "OTHER";
    }
}

openni::SensorType parse_sensor(const std::string &value) {
    if(value == "color") return openni::SENSOR_COLOR;
    if(value == "ir") return openni::SENSOR_IR;
    if(value == "depth") return openni::SENSOR_DEPTH;
    throw std::runtime_error("--sensor must be color, ir, or depth");
}

bool save_frame(const openni::VideoFrameRef &frame, const std::string &path) {
    const int width = frame.getWidth();
    const int height = frame.getHeight();
    const auto format = frame.getVideoMode().getPixelFormat();
    std::ofstream output(path, std::ios::binary);
    if(!output) return false;

    if(format == openni::PIXEL_FORMAT_RGB888) {
        output << "P6\n" << width << " " << height << "\n255\n";
        output.write(static_cast<const char *>(frame.getData()), width * height * 3);
        return output.good();
    }
    if(format == openni::PIXEL_FORMAT_GRAY8) {
        output << "P5\n" << width << " " << height << "\n255\n";
        output.write(static_cast<const char *>(frame.getData()), width * height);
        return output.good();
    }
    if(format == openni::PIXEL_FORMAT_GRAY16 ||
       format == openni::PIXEL_FORMAT_DEPTH_1_MM ||
       format == openni::PIXEL_FORMAT_DEPTH_100_UM) {
        output << "P5\n" << width << " " << height << "\n65535\n";
        const auto *source = static_cast<const std::uint16_t *>(frame.getData());
        std::vector<unsigned char> big_endian(static_cast<std::size_t>(width) * height * 2);
        for(std::size_t index = 0; index < static_cast<std::size_t>(width) * height; ++index) {
            big_endian[index * 2] = static_cast<unsigned char>(source[index] >> 8);
            big_endian[index * 2 + 1] = static_cast<unsigned char>(source[index] & 0xff);
        }
        output.write(reinterpret_cast<const char *>(big_endian.data()), big_endian.size());
        return output.good();
    }
    std::cerr << "Unsupported output pixel format: " << format_name(format) << "\n";
    return false;
}

}  // namespace

int main(int argc, char **argv) {
    std::string sensor_argument = "ir";
    std::string output_path;
    int requested_frames = 30;
    for(int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if(argument == "--sensor" && index + 1 < argc) sensor_argument = argv[++index];
        else if(argument == "--frames" && index + 1 < argc) requested_frames = std::stoi(argv[++index]);
        else if(argument == "--output" && index + 1 < argc) output_path = argv[++index];
        else {
            std::cerr << "Usage: " << argv[0]
                      << " [--sensor color|ir|depth] [--frames N] [--output image.ppm|image.pgm]\n";
            return 2;
        }
    }
    if(requested_frames < 1) {
        std::cerr << "--frames must be positive\n";
        return 2;
    }

    openni::Status status = openni::OpenNI::initialize();
    if(status != openni::STATUS_OK) {
        std::cerr << "OpenNI initialize failed: " << openni::OpenNI::getExtendedError() << "\n";
        return 3;
    }

    openni::Array<openni::DeviceInfo> devices;
    openni::OpenNI::enumerateDevices(&devices);
    std::cout << "devices=" << devices.getSize() << "\n";
    for(int index = 0; index < devices.getSize(); ++index) {
        const auto &device = devices[index];
        std::cout << "device[" << index << "] uri=" << device.getUri()
                  << " name=" << device.getName()
                  << " vendor=" << device.getVendor()
                  << " usb=" << std::hex << device.getUsbVendorId() << ":"
                  << device.getUsbProductId() << std::dec << "\n";
    }
    if(devices.getSize() == 0) {
        openni::OpenNI::shutdown();
        return 4;
    }

    openni::Device device;
    status = device.open(devices[0].getUri());
    if(status != openni::STATUS_OK) {
        std::cerr << "Device open failed: " << openni::OpenNI::getExtendedError() << "\n";
        openni::OpenNI::shutdown();
        return 5;
    }

    for(const auto sensor : {openni::SENSOR_COLOR, openni::SENSOR_IR, openni::SENSOR_DEPTH}) {
        const auto *info = device.getSensorInfo(sensor);
        std::cout << "sensor=" << sensor_name(sensor) << " available=" << (info != nullptr) << "\n";
        if(info == nullptr) continue;
        const auto &modes = info->getSupportedVideoModes();
        for(int index = 0; index < modes.getSize(); ++index) {
            const auto &mode = modes[index];
            std::cout << "  mode=" << mode.getResolutionX() << "x" << mode.getResolutionY()
                      << "@" << mode.getFps() << " format=" << format_name(mode.getPixelFormat()) << "\n";
        }
    }

    openni::SensorType sensor;
    try {
        sensor = parse_sensor(sensor_argument);
    } catch(const std::exception &error) {
        std::cerr << error.what() << "\n";
        device.close();
        openni::OpenNI::shutdown();
        return 2;
    }
    if(device.getSensorInfo(sensor) == nullptr) {
        std::cerr << "Requested sensor is unavailable: " << sensor_argument << "\n";
        device.close();
        openni::OpenNI::shutdown();
        return 6;
    }

    openni::VideoStream stream;
    status = stream.create(device, sensor);
    if(status != openni::STATUS_OK) {
        std::cerr << "Stream create failed: " << openni::OpenNI::getExtendedError() << "\n";
        device.close();
        openni::OpenNI::shutdown();
        return 7;
    }
    // Mirroring changes ArUco bit patterns and makes valid markers undecodable.
    // Robot/table coordinates require the physical, non-mirrored camera image.
    stream.setMirroringEnabled(false);

    const auto &modes = device.getSensorInfo(sensor)->getSupportedVideoModes();
    for(int index = 0; index < modes.getSize(); ++index) {
        const auto &mode = modes[index];
        const bool preferred_resolution = mode.getResolutionX() == 640 && mode.getResolutionY() == 480;
        const bool preferred_rate = mode.getFps() == 30;
        const bool preferred_format =
            (sensor == openni::SENSOR_COLOR && mode.getPixelFormat() == openni::PIXEL_FORMAT_RGB888) ||
            (sensor == openni::SENSOR_IR && (mode.getPixelFormat() == openni::PIXEL_FORMAT_GRAY8 ||
                                             mode.getPixelFormat() == openni::PIXEL_FORMAT_GRAY16)) ||
            (sensor == openni::SENSOR_DEPTH && mode.getPixelFormat() == openni::PIXEL_FORMAT_DEPTH_1_MM);
        if(preferred_resolution && preferred_rate && preferred_format) {
            stream.setVideoMode(mode);
            break;
        }
    }

    status = stream.start();
    if(status != openni::STATUS_OK) {
        std::cerr << "Stream start failed: " << openni::OpenNI::getExtendedError() << "\n";
        stream.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 8;
    }

    openni::VideoFrameRef last_frame;
    int captured = 0;
    for(int index = 0; index < requested_frames; ++index) {
        openni::VideoFrameRef frame;
        status = stream.readFrame(&frame);
        if(status != openni::STATUS_OK || !frame.isValid()) continue;
        last_frame = frame;
        ++captured;
    }
    std::cout << "captured=" << captured << "/" << requested_frames;
    if(last_frame.isValid()) {
        const auto &mode = last_frame.getVideoMode();
        std::cout << " size=" << last_frame.getWidth() << "x" << last_frame.getHeight()
                  << " format=" << format_name(mode.getPixelFormat());
    }
    std::cout << "\n";

    bool saved = output_path.empty();
    if(!output_path.empty() && last_frame.isValid()) {
        saved = save_frame(last_frame, output_path);
        std::cout << "output=" << output_path << " saved=" << saved << "\n";
    }

    stream.stop();
    stream.destroy();
    device.close();
    openni::OpenNI::shutdown();
    return captured == requested_frames && saved ? 0 : 9;
}
