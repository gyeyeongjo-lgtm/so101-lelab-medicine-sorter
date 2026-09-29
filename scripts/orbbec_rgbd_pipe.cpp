#include <OpenNI.h>

#include <atomic>
#include <cmath>
#include <cstdint>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>

namespace {

std::atomic<bool> running{true};

void stop_running(int) {
    running = false;
}

const char *status_text(openni::Status status) {
    return status == openni::STATUS_OK ? "true" : "false";
}

bool select_mode(openni::VideoStream &stream, const openni::SensorInfo *info,
                 openni::PixelFormat format, int width, int height) {
    if(info == nullptr) return false;
    const auto &modes = info->getSupportedVideoModes();
    for(int index = 0; index < modes.getSize(); ++index) {
        const auto &mode = modes[index];
        if(mode.getResolutionX() == width && mode.getResolutionY() == height &&
           mode.getFps() == 30 && mode.getPixelFormat() == format) {
            return stream.setVideoMode(mode) == openni::STATUS_OK;
        }
    }
    return false;
}

bool write_rows(const openni::VideoFrameRef &frame, int row_bytes) {
    const auto *data = static_cast<const unsigned char *>(frame.getData());
    const int stride = frame.getStrideInBytes();
    for(int row = 0; row < frame.getHeight(); ++row) {
        if(std::fwrite(data + row * stride, 1, row_bytes, stdout) !=
           static_cast<std::size_t>(row_bytes)) return false;
    }
    return true;
}

template <typename T>
bool write_scalar(const T &value) {
    return std::fwrite(&value, sizeof(value), 1, stdout) == 1;
}

}  // namespace

int main(int argc, char **argv) {
    bool info_only = false;
    bool low_bandwidth = false;
    for(int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if(argument == "--info") info_only = true;
        else if(argument == "--low-bandwidth") low_bandwidth = true;
        else {
            std::cerr << "Usage: " << argv[0] << " [--info] [--low-bandwidth]\n";
            return 2;
        }
    }
    const int width_value = low_bandwidth ? 320 : 640;
    const int height_value = low_bandwidth ? 240 : 480;
    std::signal(SIGINT, stop_running);
    std::signal(SIGTERM, stop_running);
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    // OpenNI warnings must never contaminate the binary RGB-D stdout protocol.
    openni::OpenNI::setLogConsoleOutput(false);
    if(openni::OpenNI::initialize() != openni::STATUS_OK) {
        std::cerr << "OpenNI initialize failed: " << openni::OpenNI::getExtendedError() << "\n";
        return 3;
    }
    openni::Array<openni::DeviceInfo> devices;
    openni::OpenNI::enumerateDevices(&devices);
    if(devices.getSize() == 0) {
        std::cerr << "No OpenNI device found\n";
        openni::OpenNI::shutdown();
        return 4;
    }

    const auto &device_info = devices[0];
    openni::Device device;
    if(device.open(device_info.getUri()) != openni::STATUS_OK) {
        std::cerr << "Device open failed: " << openni::OpenNI::getExtendedError() << "\n";
        openni::OpenNI::shutdown();
        return 5;
    }

    openni::VideoStream color;
    openni::VideoStream depth;
    if(color.create(device, openni::SENSOR_COLOR) != openni::STATUS_OK ||
       depth.create(device, openni::SENSOR_DEPTH) != openni::STATUS_OK) {
        std::cerr << "RGB or depth stream create failed: " << openni::OpenNI::getExtendedError() << "\n";
        color.destroy();
        depth.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 6;
    }
    if(!select_mode(color, device.getSensorInfo(openni::SENSOR_COLOR),
                    openni::PIXEL_FORMAT_RGB888, width_value, height_value) ||
       !select_mode(depth, device.getSensorInfo(openni::SENSOR_DEPTH),
                    openni::PIXEL_FORMAT_DEPTH_1_MM, width_value, height_value)) {
        std::cerr << "Required RGB888/depth-mm mode is unavailable\n";
        color.destroy();
        depth.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 7;
    }

    color.setMirroringEnabled(false);
    depth.setMirroringEnabled(false);
    const float color_hfov_rad = color.getHorizontalFieldOfView();
    const float color_vfov_rad = color.getVerticalFieldOfView();
    const float depth_hfov_rad = depth.getHorizontalFieldOfView();
    const float depth_vfov_rad = depth.getVerticalFieldOfView();
    const double color_fx_from_fov = width_value / (2.0 * std::tan(color_hfov_rad / 2.0));
    const double color_fy_from_fov = height_value / (2.0 * std::tan(color_vfov_rad / 2.0));
    const double depth_fx_from_fov = width_value / (2.0 * std::tan(depth_hfov_rad / 2.0));
    const double depth_fy_from_fov = height_value / (2.0 * std::tan(depth_vfov_rad / 2.0));
    const bool registration_supported =
        device.isImageRegistrationModeSupported(openni::IMAGE_REGISTRATION_DEPTH_TO_COLOR);
    openni::Status registration_status = openni::STATUS_NOT_SUPPORTED;
    if(registration_supported) {
        registration_status = device.setImageRegistrationMode(openni::IMAGE_REGISTRATION_DEPTH_TO_COLOR);
    }
    // This legacy Astra/driver can stop delivering frames after the first pair
    // when hardware depth-color sync is enabled. Registration is independent,
    // so keep registration enabled and pair frames by OpenNI timestamps below.
    const openni::Status sync_status = device.setDepthColorSyncEnabled(false);
    const bool hardware_sync_enabled = false;
    const auto version = openni::OpenNI::getVersion();

    if(info_only) {
        std::cout << "{"
                  << "\"device_name\":\"" << device_info.getName() << "\","
                  << "\"vendor\":\"" << device_info.getVendor() << "\","
                  << "\"uri\":\"" << device_info.getUri() << "\","
                  << "\"usb_vendor_id\":" << device_info.getUsbVendorId() << ","
                  << "\"usb_product_id\":" << device_info.getUsbProductId() << ","
                  << "\"openni_version\":\"" << version.major << "." << version.minor << "."
                  << version.maintenance << "." << version.build << "\","
                  << "\"rgb\":{\"width\":" << width_value
                  << ",\"height\":" << height_value
                  << ",\"fps\":30,\"format\":\"RGB888\","
                  << "\"hfov_rad\":" << color_hfov_rad << ","
                  << "\"vfov_rad\":" << color_vfov_rad << ","
                  << "\"fx_from_fov_px\":" << color_fx_from_fov << ","
                  << "\"fy_from_fov_px\":" << color_fy_from_fov << "},"
                  << "\"depth\":{\"width\":" << width_value
                  << ",\"height\":" << height_value << ",\"fps\":30,"
                  << "\"format\":\"DEPTH_1_MM\",\"unit\":\"mm\",\"scale_mm\":1.0,"
                  << "\"hfov_rad\":" << depth_hfov_rad << ","
                  << "\"vfov_rad\":" << depth_vfov_rad << ","
                  << "\"fx_from_fov_px\":" << depth_fx_from_fov << ","
                  << "\"fy_from_fov_px\":" << depth_fy_from_fov << "},"
                  << "\"registration_depth_to_color_supported\":"
                  << (registration_supported ? "true" : "false") << ","
                  << "\"registration_enabled\":" << status_text(registration_status) << ","
                  << "\"depth_color_sync_enabled\":"
                  << (hardware_sync_enabled ? "true" : "false") << ","
                  << "\"depth_color_sync_configured\":" << status_text(sync_status) << ","
                  << "\"pairing\":\"software_timestamp_50ms\""
                  << "}\n";
        color.destroy();
        depth.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return registration_status == openni::STATUS_OK ? 0 : 8;
    }

    if(registration_status != openni::STATUS_OK) {
        std::cerr << "Depth-to-color registration is unavailable; refusing unaligned output\n";
        color.destroy();
        depth.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 8;
    }
    if(depth.start() != openni::STATUS_OK || color.start() != openni::STATUS_OK) {
        std::cerr << "RGB or depth stream start failed: " << openni::OpenNI::getExtendedError() << "\n";
        color.stop();
        depth.stop();
        color.destroy();
        depth.destroy();
        device.close();
        openni::OpenNI::shutdown();
        return 9;
    }

    openni::VideoFrameRef color_frame;
    openni::VideoFrameRef depth_frame;
    bool have_color = false;
    bool have_depth = false;
    while(running) {
        openni::VideoStream *waiting_streams[2];
        // Some legacy OpenNI drivers stall when waitForAnyStream receives a
        // one-element array. Keep both streams in the wait set, but put the
        // missing member of the pair first so it is selected when both are ready.
        if(have_color && !have_depth) {
            waiting_streams[0] = &depth;
            waiting_streams[1] = &color;
        } else {
            waiting_streams[0] = &color;
            waiting_streams[1] = &depth;
        }
        int changed_index = -1;
        if(openni::OpenNI::waitForAnyStream(
               waiting_streams, 2, &changed_index, 2000) != openni::STATUS_OK) {
            continue;
        }
        if(waiting_streams[changed_index] == &color) {
            color_frame.release();
            have_color = color.readFrame(&color_frame) == openni::STATUS_OK && color_frame.isValid();
        } else {
            depth_frame.release();
            have_depth = depth.readFrame(&depth_frame) == openni::STATUS_OK && depth_frame.isValid();
        }
        if(!have_color || !have_depth) continue;
        if(color_frame.getWidth() != width_value || color_frame.getHeight() != height_value ||
           depth_frame.getWidth() != width_value || depth_frame.getHeight() != height_value) continue;

        const char magic[4] = {'R', 'G', 'B', 'D'};
        const std::uint32_t width = static_cast<std::uint32_t>(width_value);
        const std::uint32_t height = static_cast<std::uint32_t>(height_value);
        const std::uint64_t color_timestamp = color_frame.getTimestamp();
        const std::uint64_t depth_timestamp = depth_frame.getTimestamp();
        constexpr std::uint64_t max_pair_delta_us = 50000;
        if(color_timestamp > depth_timestamp + max_pair_delta_us) {
            depth_frame.release();
            have_depth = false;
            continue;
        }
        if(depth_timestamp > color_timestamp + max_pair_delta_us) {
            color_frame.release();
            have_color = false;
            continue;
        }
        if(std::fwrite(magic, 1, sizeof(magic), stdout) != sizeof(magic) ||
           !write_scalar(width) || !write_scalar(height) ||
           !write_scalar(color_timestamp) || !write_scalar(depth_timestamp) ||
           !write_rows(color_frame, width_value * 3) ||
           !write_rows(depth_frame, width_value * 2)) break;
        color_frame.release();
        depth_frame.release();
        have_color = false;
        have_depth = false;
    }

    color.stop();
    depth.stop();
    color.destroy();
    depth.destroy();
    device.close();
    openni::OpenNI::shutdown();
    return 0;
}
